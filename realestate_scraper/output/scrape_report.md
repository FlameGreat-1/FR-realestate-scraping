# Real Estate Scrape Report

Generated: 2026-04-22

## Overview
- Input CSV rows: 139
- Domains processed by Prefect after dedupe: 112
- Successful domains: 83
- Failed domains: 29
- Output listings rows: 1119
- Domain success rate: 74.1%
- Strict all-fields-complete rows: 0 / 1119 (0.0%)
- Average required-field completeness: 63.2%
- Median required-field completeness: 65.1%

## Field Completeness
| Field | Filled rows | Fill rate |
| --- | ---: | ---: |
| reference_id | 1119 | 100.0% |
| price | 729 | 65.1% |
| property_type | 720 | 64.3% |
| location | 1119 | 100.0% |
| surface_area | 867 | 77.5% |
| rooms | 741 | 66.2% |
| bedrooms | 673 | 60.1% |
| agency_name | 1119 | 100.0% |
| agent_name | 0 | 0.0% |
| phone | 1106 | 98.8% |
| email | 638 | 57.0% |
| coordinates | 43 | 3.8% |
| dpe_rating | 326 | 29.1% |

## Successful Domains
Top successful domains by listing count. The full domain list is in `output/domain_status_summary.csv`.

| Domain | Listings |
| --- | ---: |
| 2m-immo.com | 83 |
| mylogement.com | 69 |
| agencecoullaud.fr | 56 |
| rhpatrimoine.com | 47 |
| agencealbert1er.fr | 46 |
| ameliedherret-immo.com | 41 |
| mg-immobilier.com | 40 |
| himmo.fr | 39 |
| vivesimmobilier.fr | 39 |
| groupimmo.pro | 36 |
| vignobleimmobilier.arthurimmo.com | 34 |
| laforet.com | 33 |
| imbs-immo.com | 28 |
| groupe-tolosan-immobilier.com | 25 |
| igor-immobilier.com | 25 |
| agence-ik.fr | 22 |
| pietrapolis.fr | 22 |
| agence-foresthill.fr | 20 |
| agencexpertimmo.fr | 20 |
| vivreici.com | 20 |
| agencedeneuville.com | 18 |
| lgo-immobilier.fr | 18 |
| agencemathieu.fr | 17 |
| momvacances.com | 16 |
| maisonsoxygene.com | 15 |
| ...and 58 more successful domains | |

## Unsuccessful Domains
These domains did not produce usable listings, and the reason column explains why.

| Domain | Status | Reason |
| --- | --- | --- |
| 4mlagence.fr | blocked | HTTP probe returned 403; Playwright also found no usable listings |
| beausejour-immobilier.fr | blocked | HTTP probe returned 403; Playwright also found no usable listings |
| dunkerque.stephaneplazaimmobilier.com | blocked | HTTP probe returned 403; Playwright also found no usable listings |
| erapontdelarc.com | blocked | HTTP probe returned 403; Playwright also found no usable listings |
| lagencetoulousaine.fr | blocked | HTTP probe returned 403; Playwright also found no usable listings |
| stephaneplazaimmobilier.com | blocked | HTTP probe returned 403; Playwright also found no usable listings |
| agence-odeia-immobilier.com | error | Page.evaluate: Execution context was destroyed, most likely because of a navigation |
| carmen-immobilier.com | error | Page.evaluate: Execution context was destroyed, most likely because of a navigation |
| cote-immobilier.com | error | Page.evaluate: Execution context was destroyed, most likely because of a navigation |
| idimmo31.idimmo.net | error | Page.evaluate: Execution context was destroyed, most likely because of a navigation |
| abacusfinance.com | no_listings | Could not find listings on site with either method |
| capwestresidence.fr | no_listings | Could not find listings on site with either method |
| immobiliere-abc.com | no_listings | Could not find listings on site with either method |
| maisonbianchi.eu | no_listings | Could not find listings on site with either method |
| tit-immobilier.com | no_listings | Could not find listings on site with either method |
| agencedubrivet.com | unreachable | Site did not respond to HTTP probe and Playwright found no usable listings |
| arp-immo.fr | unreachable | Site did not respond to HTTP probe and Playwright found no usable listings |
| capsud-immo.com | unreachable | Site did not respond to HTTP probe and Playwright found no usable listings |
| galyo.fr | unreachable | Site did not respond to HTTP probe and Playwright found no usable listings |
| gardnerimmobilier.com | unreachable | Site did not respond to HTTP probe and Playwright found no usable listings |
| grisel-immobilier.fr | unreachable | Site did not respond to HTTP probe and Playwright found no usable listings |
| homeconseils31.com | unreachable | Site did not respond to HTTP probe and Playwright found no usable listings |
| immobiliere-de-croix.com | unreachable | Site did not respond to HTTP probe and Playwright found no usable listings |
| immograndlyon.com | unreachable | Site did not respond to HTTP probe and Playwright found no usable listings |
| invalid | unreachable | Site did not respond to HTTP probe and Playwright found no usable listings |
| laresidence.fr | unreachable | Site did not respond to HTTP probe and Playwright found no usable listings |
| parfumdimmobilier.fr | unreachable | Site did not respond to HTTP probe and Playwright found no usable listings |
| well-estate.fr | unreachable | Site did not respond to HTTP probe and Playwright found no usable listings |
| wretmanestate.com | unreachable | Site did not respond to HTTP probe and Playwright found no usable listings |

## What The Numbers Mean
- `reference_id`, `location`, `agency_name`, and `phone` are strong in the current output.
- `coordinates` and `dpe_rating` are sparse, so they should be treated as partial enrichment rather than fully reliable coverage.
- `agent_name` is currently empty for all rows, so it is not yet being extracted by the scraper.
- Exact correctness cannot be proven from CSVs alone; the completeness numbers above are the best automated proxy for accuracy.

## Files
- `output/listings_consolidated.csv`
- `output/error_log.csv`
- `output/domain_status_summary.csv`
