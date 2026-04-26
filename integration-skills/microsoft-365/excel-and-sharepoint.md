# Microsoft 365: Excel + SharePoint

## Node types

- `n8n-nodes-base.microsoftExcel` — read/write/append Excel rows on workbooks accessible via Microsoft Graph
- `n8n-nodes-base.microsoftSharepoint` — read/write SharePoint files, list items, etc.
- `n8n-nodes-base.microsoftOutlook` — email send/list/move
- `n8n-nodes-base.microsoftTeams` — chat / channel post

All four share the same OAuth credential (typically named `<env>_ms_oauth`).

## Credential block

```json
"credentials": {
  "microsoftOAuth2Api": {
    "id": "{{HYDRATE:env:credentials.msOauth.id}}",
    "name": "{{HYDRATE:env:credentials.msOauth.name}}"
  }
}
```

The exact credential type key depends on the node — Excel uses `microsoftExcelOAuth2Api`, SharePoint uses `microsoftSharePointOAuth2Api`. Check by adding the node in the n8n UI once and inspecting the resulting JSON.

## Resource paths

Use `{{HYDRATE:env:sharepoint.driveId}}` and `{{HYDRATE:env:sharepoint.paths.<key>}}` from YAML. Concrete shape from `dev.yaml`:

```yaml
sharepoint:
  driveId: "b!real-drive-id-here"
  paths:
    reportFile: "/Reports/monthly_data.xlsx"
    poDataFile: "/PurchaseOrders/po_data.xlsx"
```

## Common quirks

- **`driveId` vs `siteId`.** SharePoint exposes both. Excel nodes typically want `driveId` (the OneDrive-style identifier). SharePoint list-item nodes want `siteId`. Don't swap them.
- **Path encoding.** Spaces in path: use literal spaces in the YAML, n8n handles URL-encoding. Don't pre-encode (`%20`) — that double-encodes.
- **Token expiry.** OAuth tokens refresh automatically as long as the credential has a valid refresh token. If you see `401 Unauthorized` repeatedly, re-authorize the credential in the n8n UI; the refresh chain may have broken.
- **Excel range writing.** Setting `range: "A1"` writes a single cell; `range: "A1:Z100"` overwrites the rectangle. Append-row mode finds the next empty row automatically.

## Worked example

`periodic_excel_report.template.json` reads `monthly_data.xlsx` from SharePoint, summarizes via OpenRouter, then sends a Gmail. The Excel read block:

```json
{
  "type": "n8n-nodes-base.microsoftExcel",
  "parameters": {
    "operation": "getRows",
    "workbook": "{{HYDRATE:env:sharepoint.driveId}}",
    "worksheet": "Sheet1",
    "filePath": "{{HYDRATE:env:sharepoint.paths.reportFile}}"
  }
}
```
