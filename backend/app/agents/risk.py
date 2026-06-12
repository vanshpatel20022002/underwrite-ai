from datetime import date, timedelta
from pathlib import Path

from app.schemas.case import ImageConditionNote, RiskFlag

RISK_PROMPTS = {
    "damaged_roof": "damaged roof on residential house",
    "poor_exterior": "poor exterior condition deteriorating house",
    "construction": "house under construction incomplete building",
    "vacant_lot": "empty vacant lot no building",
}


def analyze_images(image_paths: list[str]) -> list[ImageConditionNote]:
    notes: list[ImageConditionNote] = []
    try:
        from PIL import Image
        import torch
        import open_clip

        model, _, preprocess = open_clip.create_model_and_transforms(
            "ViT-B-32", pretrained="openai"
        )
        tokenizer = open_clip.get_tokenizer("ViT-B-32")
        model.eval()

        text_tokens = tokenizer(list(RISK_PROMPTS.values()))
        with torch.no_grad():
            text_features = model.encode_text(text_tokens)
            text_features /= text_features.norm(dim=-1, keepdim=True)

        for path in image_paths:
            if not Path(path).exists():
                continue
            image = preprocess(Image.open(path).convert("RGB")).unsqueeze(0)
            with torch.no_grad():
                image_features = model.encode_image(image)
                image_features /= image_features.norm(dim=-1, keepdim=True)
                sims = (image_features @ text_features.T).squeeze(0)

            best_idx = int(sims.argmax())
            best_score = float(sims[best_idx])
            condition = list(RISK_PROMPTS.keys())[best_idx]
            risk_level = "high" if best_score > 0.28 else "medium" if best_score > 0.22 else "low"

            notes.append(
                ImageConditionNote(
                    image_path=path,
                    condition=condition.replace("_", " "),
                    risk_level=risk_level,
                    confidence=round(best_score, 3),
                )
            )
    except Exception:
        for path in image_paths:
            notes.append(
                ImageConditionNote(
                    image_path=path,
                    condition="not analyzed",
                    risk_level="low",
                    confidence=0.0,
                )
            )
    return notes


def evaluate_risk(
    subject: dict,
    comps: list,
    ml_estimate: float | None,
    image_notes: list[ImageConditionNote],
    has_zoning: bool,
) -> tuple[float, list[RiskFlag]]:
    flags: list[RiskFlag] = []
    score = 20.0

    if not has_zoning:
        flags.append(
            RiskFlag(
                code="MISSING_ZONING",
                severity="medium",
                message="Zoning document not provided",
            )
        )
        score += 15

    stale = [
        c
        for c in comps
        if (date.today() - c.sale_date).days > 365
    ]
    if stale:
        flags.append(
            RiskFlag(
                code="STALE_COMPS",
                severity="medium",
                message=f"{len(stale)} comparable(s) older than 12 months",
            )
        )
        score += 10 * min(len(stale), 3)

    if comps and ml_estimate:
        comp_median = sorted(c.adjusted_price or c.sale_price for c in comps)[len(comps) // 2]
        deviation = abs(ml_estimate - comp_median) / max(comp_median, 1)
        if deviation > 0.25:
            flags.append(
                RiskFlag(
                    code="PRICE_DEVIATION",
                    severity="high",
                    message=f"ML estimate deviates {deviation:.0%} from comp median",
                    evidence=f"ML: ${ml_estimate:,.0f}, Comps median: ${comp_median:,.0f}",
                )
            )
            score += 25

    high_risk_images = [n for n in image_notes if n.risk_level == "high"]
    if high_risk_images:
        flags.append(
            RiskFlag(
                code="IMAGE_CONDITION",
                severity="high",
                message=f"{len(high_risk_images)} image(s) show elevated condition risk",
            )
        )
        score += 20

    if "zoning" in subject.get("borrower_notes", "").lower() and not has_zoning:
        flags.append(
            RiskFlag(
                code="BORROWER_ZONING_MISMATCH",
                severity="medium",
                message="Borrower mentions zoning but no zoning doc uploaded",
            )
        )
        score += 10

    return min(100.0, score), flags
