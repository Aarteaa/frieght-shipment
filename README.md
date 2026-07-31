# Shipment Analytics Dashboard

A Streamlit dashboard analyzing 5,000 shipments to answer five operational questions for FreightFox: regional delivery performance, the freight cost/distance relationship and carrier pricing outliers, which customers see the most delays, data quality issues in the source file, and a proposed leading indicator for catching problems early.

**Live dashboard:** https://frieght-shipment-fjduqusxgrx86w8egb9teq.streamlit.app/

## Running locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

`shipments.csv` needs to sit in the same folder as `app.py`.

## Approach

I didn't take the dataset's own status labels at face value. Early on I found that the `status` column (Delivered/Delayed/etc.) barely correlates with what the dates actually show — roughly half of "Delivered" shipments were, by date math, actually late, and vice versa for "Delayed." So every delay and on-time figure in this dashboard is computed directly from `promised_delivery_date` vs. `actual_delivery_date`, never from the status label.

I also ran significance tests before drawing conclusions from any group comparison (region, mode, carrier). Region and mode don't hold up statistically — the differences you see are within the range of random noise. Carrier is the one dimension that clears a basic significance bar, and one specific carrier (CARR_07) is a clear, large outlier on pricing.

Full reasoning and every number is in `BUSINESS_ANSWERS.md`, with the underlying calculation shown for each answer.

## Data quality caveats (short version, full version in `BUSINESS_ANSWERS.md`)

- South region has actual delivery dates recorded for only ~15% of resolved shipments (vs. 100% elsewhere) — flagged as low-confidence throughout.
- `status` label doesn't reliably reflect actual lateness (see above).
- 72 shipments show delivery before pickup — treated as invalid and excluded.
- `delivery_date` is a duplicate of `promised_delivery_date` — dropped.
- 15 duplicate shipment IDs — deduplicated before analysis.

## Stack

Python, pandas, Streamlit, Plotly, scipy (significance testing), scikit-learn (regression).
