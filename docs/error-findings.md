# Errors the independent engine found

_Checked against the imported Okafor-Lindqvist 2025 packet on 2026-10-16. These rows are findings stored by `run_validation()`, not cards written into the UI. A second scan created 0 new rows and kept the reviewer decision on the Northlake finding._

Return lines were not changed. Tax effects, where shown, are estimates from `tax_effect_rates` on v3.

## Known examples the rules discovered

| Finding | Rule | What disagreed | Evidence |
|---|---|---|---|
| Possible duplicate interest, $1,840 | `DUP-INCOME` | `SchB.1.1` (D28 Northlake Securities composite 1099, field `int_1`, `ev-0492`) and `SchB.1.2` (D29 Northlake Bank 1099-INT box 1, `ev-0538`) both report 1,840.00. Shared issuer token `northlake`. Schedule B total interest `SchB.2` is 6,450 and includes both. | `ev-0492`, `ev-0538`, D28, D29 |
| FX rate year on `SchB.1.6` | `FX-YEAR` | The line cites `ref:fx.SEK.2024_average` = 10.56 for tax year 2025. `2025_average` is 9.86. SEK 18,450.00 (`ev-0960`, D36) / 9.86 rounds to 1,871 USD; the engine stored 1,747. Estimated federal effect of the 124 difference is about $43. | `ref:fx.SEK.2024_average`, `ev-0960`, `SchB.1.6` |
| SSN mismatch for Theo | `IDENTITY-SSN` | Household person `theo` ends 3309. The 2024 dependent record ends 3390. Supporting extracts `ev-0012` (D06) and `ev-1080` (D71) match the prior-year value. Category `needs_judgment`. Full SSNs are not stored in the finding. | `household:theo`, `py:/return_2024/dependents`, `ev-0012`, `ev-1080` |

Daniel Ortiz (`st-02`) marked the duplicate-interest finding verified in the browser. Status is `resolved`. `SchB.1.1` remains 1,840. A preparer attempt to mark it a false positive was rejected.

## Other discrepancies from the same scan

| Rule | Finding | Why it was raised |
|---|---|---|
| `EXTRACT-PRINTED` | `ev-1049` on D64 | Extracted 1,500.00 is not a number on the printed page. The page shows an ambiguous first digit (`$?,500.00`). Confidence 0.41. Also raised as `LOW-CONFIDENCE`, and the value is cited by `SchA.11`. |
| `ARITH-BROKER` | D31 summary vs lots | `ev-0703` summary proceeds 71,965. Sum of 17 extracted lot proceeds is 71,715 (difference 250). Superseded D30 was skipped. |
| `MISSING-BASIS` / `LOW-CONFIDENCE` | `ev-0919` on D35 | Crypto field `C6_basis` has no amount (confidence 0.60). Cited by `F8949.H.C6`. Reported zero basis on RSU lots was not flagged. |
| `SUPERSEDED` | D30 vs corrected D31 | Same issuer and form. Four shared fields differ: M6 wash 735 → 512, M9 basis 6,900 → 4,880, M14 acquired 2024-10-15 → 2024-09-15, M14 term short → long. No current-version line cites D30. |
| `PARTIAL-EXTRACT` | D31 | Extraction status is partial. D30 is superseded, so it was not flagged again. |
| `YOY` | `F1040.11`, `F1040.15`, `F1040.24` | Change exceeds the firm threshold (10% and $1,000). Informational. Prior-year AGI 228,409 vs 445,590; taxable income 182,465 vs 346,913; tax 37,557 vs 81,962. |

The scan stored 13 findings. Engine diagnostics on the overview remain separate leads; they are not the finding records.
