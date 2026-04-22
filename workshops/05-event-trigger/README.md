# Workshop 05 — Event-Based Trigger

Wire the pipeline to `Microsoft.Storage.BlobCreated` events so every CSV landing in `incoming/` triggers ingestion automatically.

**Prerequisite:** [Workshop 04](../04-data-pipeline/) complete
**Next:** [Workshop 06 — Simulate Ingestion](../06-simulate-ingestion/)

---

## 5.1 Create the trigger

1. Open pipeline `pl_ingest_DepositMovement`.
2. **Home** ribbon → **Trigger** → **Add storage event trigger**.
3. Choose **Azure Blob events**.
4. Pick the **subscription** and **storage account** from Workshop 01.
5. A new **Eventstream** object is created in the workspace — keep the default name or set `es-adls-blobcreated`.
6. **Event type:** `Microsoft.Storage.BlobCreated`.

## 5.2 Subject filters

| Filter | Value |
|---|---|
| Begins with | `/blobServices/default/containers/intraday-deposits/blobs/incoming/` |
| Ends with | `.csv` |
| Ignore case | ✅ |

This excludes sidecars (`.tmp`, `.crc`, `_SUCCESS`, etc.) and fires **only** for CSVs in `incoming/`.

## 5.3 Trigger → pipeline parameter mapping

| Pipeline parameter | Value |
|---|---|
| `pFileName` | `@triggerBody().FileName` *(or leave blank — pipeline uses `@pipeline()?.TriggerEvent?.FileName`)* |
| `pFolder` | `incoming` |

## 5.4 Name and create

Trigger name (Reflex item): `tg_blobcreated_deposit`. Select **Create**.

## 5.5 Validate (via Azure Portal upload)

1. **[portal.azure.com](https://portal.azure.com)** → open the storage account → **Data storage** → **Containers** → `intraday-deposits`.
2. Click into `incoming/` folder (or create it via **+ Add Directory**).
3. Top toolbar → **Upload** → pick `resources/datasets/mock_0030_0100.csv` from your local copy of this repo → **Upload**.
4. Switch to **Fabric Portal** → left nav → **Monitor** (Monitor hub) → **Pipeline runs**.
5. Within ~15 seconds, a new run of `pl_ingest_DepositMovement` should appear and complete **Succeeded**.

## ✅ Exit Criteria

- [ ] Eventstream + Reflex trigger exist in workspace
- [ ] Trigger fires on `.csv` landing in `incoming/`
- [ ] Pipeline completes with 1 `Success` row in `ProcessedFiles`

→ Proceed to **[Workshop 06 — Simulate Ingestion](../06-simulate-ingestion/)**
