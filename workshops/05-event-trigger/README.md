# Workshop 05 — Event-Based Trigger

Wire the pipeline to `Microsoft.Storage.BlobCreated` events so every CSV landing in `incoming/` triggers ingestion automatically.

**Prerequisite:** [Workshop 04](../04-data-pipeline/) complete  
**Next:** [Workshop 06 — Simulate Ingestion](../06-simulate-ingestion/)

---

## 5.1 Open the trigger panel

1. Open pipeline **`pl_ingest_DepositMovement`**.
2. **Home** ribbon → **Trigger** → **Add trigger**.
3. The **"Add rule"** panel opens on the right side.

## 5.2 Fill in rule details

In the **Details** section:

| Field | Value |
|---|---|
| **Rule name** | `rule_new_files_created_deposit` |

## 5.3 Connect the event source (Monitor)

1. Under **Monitor** → click **"Select source events"**.
2. The **Real-Time hub** "Select a data source" panel opens.
3. Select **Azure Blob Storage events**.

### 5.3.1 Configure connection settings

The **"Configure connection settings"** wizard opens (3-step: Configure → Configure alert → Review + connect).

**Step 1 — Configure:**

| Field | Value |
|---|---|
| Storage account | ● Connect to existing Azure Blob Storage account |
| Subscription | *(select your workshop subscription)* |
| Azure Blob Storage account | `rtistorage01` |

On the right **Stream details** panel:
- **Workspace**: `RTI-IntradayDepositMovement` (should be auto-selected)
- **Eventstream name**: click the pencil icon ✏️ and rename to **`es_adls_blobcreated`**

Click **Next**.

### 5.3.2 Configure alert — event type and filters

**Step 2 — Configure alert:**

| Field | Value |
|---|---|
| **Event type(s)** | `Microsoft.Storage.BlobCreated` *(default)* |

Under **Set filters**, add two filter rows:

| # | Field | Operator | Value |
|---|---|---|---|
| 1 | `subject` | `String begins with` | `/blobServices/default/containers/intraday-deposits/blobs/incoming/` |
| 2 | `subject` | `String ends with` | `.csv` |

> 💡 **Why these filters?** The first filter scopes to blobs in the `incoming/` folder of the `intraday-deposits` container. The second excludes sidecars (`.tmp`, `.crc`, `_SUCCESS`, etc.) and fires **only** for CSV files.

Click **Next**.

### 5.3.3 Review + connect

**Step 3 — Review + connect:**

Verify the summary:

| Setting | Expected |
|---|---|
| Event source type | Azure Blob Storage events |
| Subscription | *(your subscription)* |
| Azure Blob Storage account | `rtistorage01` |
| Event types | Microsoft.Storage.BlobCreated |
| Event filters | subject StringBeginsWith `.../intraday-deposits/blobs/incoming/` |
| | subject StringEndsWith `.csv` |
| Workspace | RTI-IntradayDepositMovement |
| Eventstream name | `es_adls_blobcreated` |

Click **Connect**.

Wait for all three tasks to complete:

| Task | Expected status |
|---|---|
| Create Azure blob storage system events | ✅ Successful |
| Create Eventstream | ✅ Successful |
| Link Azure blob storage system events to Fabric events | ✅ Successful |

Click **Save** to return to the "Add rule" panel.

## 5.4 Verify action and parameters

Back on the **"Add rule"** panel, verify:

**Action** section — pre-populated from the pipeline:

| Field | Value |
|---|---|
| Select action | Run Pipeline |
| Fabric item | `pl_ingest_DepositMovement` / RTI-IntradayDepositMovement |

**Parameters** section — auto-mapped event properties:

| Parameter | Type | Mapped to |
|---|---|---|
| Type | String | `__type` |
| Subject | String | `__subject` |
| Source | String | `__source` |

> 💡 **About `__subject`:** The `Subject` parameter receives the full blob path, e.g.  
> `/blobServices/default/containers/intraday-deposits/blobs/incoming/mock_0030_0100.csv`  
> The pipeline extracts just the filename using `@last(split(pipeline().parameters.Subject, '/'))`.

## 5.5 Save location and create

In the **Save location** section:

| Field | Value |
|---|---|
| Workspace | `RTI-IntradayDepositMovement` |
| Item | Create a new item |
| New item name | `tg_blobcreated_deposit` |

Click **Create**.

The **Rules** panel shows:

```
rule_new_files_created_deposit   [New]   🟢 Running
```

The trigger is now live.

## 5.6 Workspace items created

After completing this workshop, your workspace now has two new items:

| Item | Type | Purpose |
|---|---|---|
| `es_adls_blobcreated` | Eventstream | Receives Azure Blob Storage events from `rtistorage01` |
| `tg_blobcreated_deposit` | Activator (Reflex) | Contains the rule that triggers the pipeline on new CSV files |

## 5.7 Validate (via Azure Portal upload)

1. **[portal.azure.com](https://portal.azure.com)** → open storage account `rtistorage01` → **Data storage** → **Containers** → `intraday-deposits`.
2. Click into the `incoming/` folder (or create it via **+ Add Directory**).
3. Top toolbar → **Upload** → pick `resources/datasets/mock_0030_0100.csv` from your local copy of this repo → **Upload**.
4. Switch to **Fabric Portal** → left nav → **Monitor** (Monitor hub) → **Pipeline runs**.
5. Within ~30 seconds a new run of `pl_ingest_DepositMovement` should appear and complete **Succeeded**.

> ⚠️ **First trigger may take 1–2 minutes.** The Eventstream needs to warm up on first use. Subsequent triggers fire within seconds.

## ✅ Exit Criteria

- [ ] Eventstream `es_adls_blobcreated` exists in workspace
- [ ] Activator `tg_blobcreated_deposit` exists and shows **Running**
- [ ] Trigger fires on `.csv` landing in `incoming/`
- [ ] Pipeline completes with 1 `Success` row in `wh_control_framework.dbo.ProcessedFiles`

→ Proceed to **[Workshop 06 — Simulate Ingestion](../06-simulate-ingestion/)**
