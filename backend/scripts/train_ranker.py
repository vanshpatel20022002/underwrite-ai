"""Train comparable ranking model from seeded property data."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import async_session_factory
from app.geo.comp_search import search_comparables
from app.ml.ranker import train_ranker


async def main():
    subjects = [
        {
            "address": "15 DEERMEADE PL SE, Calgary, AB",
            "property_type": "single_family",
            "bedrooms": 3,
            "bathrooms": 2.0,
            "square_footage": 1800,
            "year_built": 1981,
            "latitude": 50.9219,
            "longitude": -114.0041,
        },
        {
            "address": "100 8 AVE SW, Calgary, AB",
            "property_type": "condo",
            "bedrooms": 2,
            "bathrooms": 1.5,
            "square_footage": 1100,
            "year_built": 2010,
            "latitude": 51.046,
            "longitude": -114.065,
        },
    ]

    all_comps = []
    async with async_session_factory() as session:
        for subject in subjects:
            comps = await search_comparables(session, subject, radius_miles=10.0, limit=20)
            all_comps.append(comps)

    result = train_ranker(subjects, all_comps)
    print(f"Ranker training result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
