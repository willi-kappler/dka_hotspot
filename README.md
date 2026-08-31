# DKA Hotspot Analysis

This project investigates where diabetic ketoacidosis (DKA) occurs at the first
manifestation of type 1 diabetes in children and adolescents. The goal is to
identify regional hotspots and support targeted awareness campaigns. The pilot
covers Tübingen, Reutlingen and Zollernalbkreis in Baden-Württemberg.

## What the app does

The app imports case data that have already been pseudonymized by participating
clinics and calculates DKA severity from pH and bicarbonate. It maps cases around
postcode centroids and provides analyses by time, age, sex, district and GISD
deprivation. Clinic and paediatric-practice locations can be displayed for
geographic context.

## Data sources

- **Clinical case data** — provided in pseudonymized form by the participating
  diabetes clinics in Tübingen and Reutlingen.
- **Socioeconomic deprivation** — postcode-level GISD data derived from the
  [Robert Koch Institute GISD dataset](https://robert-koch-institut.github.io/German_Index_of_Socioeconomic_Deprivation_GISD/).
- **District boundaries** —
  [BKG Administrative Areas 1:250,000 (VG250)](https://gdz.bkg.bund.de/index.php/default/open-data/wfs-verwaltungsgebiete-1-250-000-stand-01-01-wfs-vg250.html).
- **Postcode coordinates** — generated using the
  [Geoapify Geocoding API](https://www.geoapify.com/geocoding-api/).
- **Paediatric practices** — scraped from the public
  [Kassenärztliche Vereinigung Baden-Württemberg physician search](https://www.arztsuche-bw.de/)
  on 13 August 2026.
- **Hospitals** — extracted from the
  [Bundes-Klinik-Atlas Open Data](https://bundes-klinik-atlas.de/open-data/).
