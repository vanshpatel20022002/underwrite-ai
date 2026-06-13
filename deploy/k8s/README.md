# Kubernetes Deployment — Underwriting Platform

> **Docker Compose remains the recommended path for local development and demos.**
> See the root `README.md` and `docker-compose.yml`.
>
> These manifests are provided as a **local/staging-style demo** of production-shaped
> Kubernetes deployment. They are **not hardened for production** — no TLS, no network
> policies, no resource limits tuned for real workloads, no secret management beyond
> basic Kubernetes Secrets.

---

## Prerequisites

| Tool | Version tested | Install |
|---|---|---|
| `kubectl` | 1.28+ | https://kubernetes.io/docs/tasks/tools/ |
| `kind` | 0.22+ | https://kind.sigs.k8s.io/docs/user/quick-start/ |
| `minikube` | 1.32+ | https://minikube.sigs.k8s.io/docs/start/ |
| Docker | 24+ | https://docs.docker.com/get-docker/ |

You only need **one** of kind or minikube — not both.

---

## 1. Build the application images

From the repository root:

```bash
# API + Celery worker (same image)
docker build -f docker/Dockerfile.api -t underwriting-api:latest .

# Next.js frontend
# NEXT_PUBLIC_API_URL is baked in at build time.
# For a local cluster with port-forwarding, keep it as localhost:8000.
docker build -f docker/Dockerfile.frontend \
  --build-arg NEXT_PUBLIC_API_URL=http://localhost:8000 \
  -t underwriting-frontend:latest .
```

---

## 2. Load images into the cluster

### kind

```bash
kind create cluster --name underwriting   # skip if cluster already exists
kind load docker-image underwriting-api:latest --name underwriting
kind load docker-image underwriting-frontend:latest --name underwriting
```

### minikube

```bash
minikube start
minikube image load underwriting-api:latest
minikube image load underwriting-frontend:latest
```

---

## 3. Create the Secret

**Never commit real keys.** Create a `secret.yaml` from the example, fill it in, and apply it:

```bash
cp deploy/k8s/secret.example.yaml deploy/k8s/secret.yaml
# Edit secret.yaml — replace placeholder values with real ones
```

Or generate directly from your `.env` file:

```bash
kubectl create namespace underwriting  # if not yet created

kubectl create secret generic underwriting-secrets \
  --namespace underwriting \
  --from-literal=POSTGRES_PASSWORD="$(grep POSTGRES_PASSWORD .env | cut -d= -f2)" \
  --from-literal=GROQ_API_KEY="$(grep GROQ_API_KEY .env | cut -d= -f2)" \
  --from-literal=OPENAI_API_KEY="$(grep OPENAI_API_KEY .env | cut -d= -f2)"
```

---

## 4. Apply the manifests

Apply in dependency order:

```bash
kubectl apply -f deploy/k8s/namespace.yaml
kubectl apply -f deploy/k8s/configmap.yaml
kubectl apply -f deploy/k8s/secret.yaml        # your filled-in copy — NOT secret.example.yaml
kubectl apply -f deploy/k8s/postgres.yaml
kubectl apply -f deploy/k8s/redis.yaml
kubectl apply -f deploy/k8s/qdrant.yaml
kubectl apply -f deploy/k8s/api.yaml
kubectl apply -f deploy/k8s/worker.yaml
kubectl apply -f deploy/k8s/frontend.yaml
```

Or apply everything at once (namespace and configmap/secret must already exist):

```bash
kubectl apply -f deploy/k8s/namespace.yaml
kubectl apply -f deploy/k8s/configmap.yaml
kubectl apply -f deploy/k8s/secret.yaml
kubectl apply -f deploy/k8s/ --recursive
```

---

## 5. Wait for pods to be ready

```bash
kubectl get pods -n underwriting --watch
```

All pods should reach `Running` status. Postgres and Redis start fastest; the API pod
waits for its readiness probe to pass before receiving traffic.

---

## 6. Port-forward to access the services

Open two separate terminals:

```bash
# Terminal 1 — API
kubectl port-forward svc/api 8000:8000 -n underwriting

# Terminal 2 — Frontend
kubectl port-forward svc/frontend 3000:3000 -n underwriting
```

Then open **http://localhost:3000** in your browser.

The API health endpoint is at **http://localhost:8000/health**.

---

## 7. Tear down

```bash
# Delete all resources in the namespace
kubectl delete namespace underwriting

# Delete the cluster entirely (kind)
kind delete cluster --name underwriting

# Delete the cluster entirely (minikube)
minikube delete
```

---

## Notes

- `imagePullPolicy: Never` is set in `api.yaml`, `worker.yaml`, and `frontend.yaml` so that
  kind/minikube uses the locally loaded image instead of pulling from a registry. Remove
  that line and replace image tags with registry paths when deploying to a remote cluster.

- `NEXT_PUBLIC_API_URL` is a Next.js public env var — it is embedded into the JavaScript
  bundle **at build time**. Changing the ConfigMap after the image is built has no effect.
  Rebuild the frontend image if the API URL changes.

- These manifests use the default `standard` StorageClass (provided by kind and minikube).
  On a real cluster, replace the PVCs with your preferred StorageClass.

- No Ingress is included. Add one with your preferred controller (nginx-ingress, Traefik,
  etc.) if you want hostname-based routing instead of port-forwarding.
