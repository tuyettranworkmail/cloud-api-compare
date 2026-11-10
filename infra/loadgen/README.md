# T2: Google Cloud k6 load generator

This is a **standalone Terraform root module** for one dedicated GCE load generator in `asia-southeast1`. It installs `k6`, Python 3, and Git at first boot. It does **not** deploy API targets, seed Firestore, run tests, or grant IAM permissions.

## Prerequisites

- The infrastructure owner approves project, VPC subnet, budget, existing service account and IAM grants.
- Terraform >=1.5, gcloud with Application Default Credentials, Compute Engine API enabled.
- An existing subnet in the selected region, with Cloud NAT **or** an approved external egress IP for the startup package download.
- OS Login/IAP or approved administrative access to the VM. No inbound firewall rules are created here.
- For private Cloud Run or Gen2 Functions, the service account must be explicitly authorized as invoker by the application owner.
- IAM roles for cloud metrics/logs should be read-only and scoped to actual collector needs; never commit tokens or service-account keys.

## Windows PowerShell (from the project root)

```powershell
cd .\infra\loadgen
Copy-Item terraform.tfvars.example terraform.tfvars
notepad terraform.tfvars
gcloud auth application-default login
terraform init
terraform fmt -check
terraform validate
terraform plan -out=loadgen.tfplan
```

Review the plan and its billing/network consequences with the team **before**:

```powershell
terraform apply loadgen.tfplan
terraform output
```

Terraform state may contain sensitive infrastructure metadata: keep it outside Git, use an approved remote state backend for shared deployment, and never commit `.tfstate`/`.tfvars`.

## Verify installation and connectivity

Use approved IAP/OS Login access, for example (if IAM, SSH and firewall policy permit):

```powershell
gcloud compute ssh benchmark-loadgen --project YOUR_GCP_PROJECT_ID --zone asia-southeast1-b --tunnel-through-iap
```

On the VM:

```bash
k6 version
cat /opt/benchmark/k6-version.txt
curl -sS -o /dev/null -w 'HTTP %{http_code}\n' --max-time 15 https://YOUR_IAAS_HOST/openapi.json
```

`401/403` indicates connectivity but may require a valid identity token. Confirm endpoint path, authorization, same region and response semantics with the API owner. Do not send benchmark write requests until Firestore seed namespace and write permissions have been verified.

## Handoff evidence (T2)

Save: `terraform validate` and reviewed plan outputs, VM name/ID/zone, `k6 version`, startup log (`sudo journalctl -u google-startup-scripts.service`), connectivity HTTP status, source Git SHA and timestamp. Share no access tokens or private-key material.

**Completion definition:** T2 `apply infra/loadgen` is complete only after a successful real apply and verification on GCP; these files alone are an implementation prepared for deployment.
