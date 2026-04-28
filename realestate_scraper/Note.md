
YOU HAVE FULL AND COMPLETE READ AND WRITE ACCESS TO THE REPO FROM MY OTHER ACCOUNT BECAUSE I HAVE ADDED YOU AS A GROUP MEMEBER WITH A DEVELOPER ROLE:

https://gitlab.com/scrap-group/scrap-project

SO IT MEANS YOU CAN EXAMINE FILES, MODIFY, CREATE AND IMPLEMENT, COMMIT AND CREATE MERGE REQUEST ETC

CRITICAL: EVERYTHING IS ON THE MAIN BRANCH. 

DO NOT FOOLSIHLY START LISTING WHAT IS ON THE MASTER BRANCH

HERE IS EXACTLY WHAT I WANT YOU TO DO:

NOW WE ARE GOING TO WORK ON THIS TEST CODEBASE GIVEN TO ME.

THE CURRENT CODEBASE IS EXACTLY WHAT I HAVE DONE

THERE ARE OVER 200+ PARTICIPANT AND MY GOAL TO ACHIEVE 1ST POSITION AND NOTHING LESS THAN 1ST POSITION.
SO AS A SENIOR BACKEND ENGINEER WITH CCOMBINED EXPERTISE ON SCRAPING, AUTOMATION, OPTIMIZATION, CODE QUALITY, SCALABILITY ETC YOU ARE GOING TO WORK WITH ME TO ACHIEVE THIS .

REQUIREMENTS AND INSTRUCTIONS GIVEN IS AT THE /rules/

DATA GIVEN ONLY IS AT THE /data/. 


THE PROBLEM NOW IS THAT WHEN I RUN IT HANGS, TIMESOUT AND RETURNS NO LISTING. BUT THE ORIGINAL CODEBASE WAS TAKING JUST 3 MINUUTES MAX TO COMPLETE AND RETURNS ABOUT 400+ LISTINGS


I WANT YOU  TO EXAMINE THE ENTIRE CODEBASE DEEPLY AND THOROUGHLY TO FIGURE OUT THE ISSUE AND ADDRESS IT.

AVOID PATCH WORK

AVOID GUESSING

AVOID ASSUMPTIONS

WE ARE TALKING ABOUT REAL ENGINEERING HERE NOT JOKES.

AND THE MAIN FOCUS IS ON RUNTIME SPEED, ACCURCACY AND SCALABILITY




(venv) softverse@Softverse:~/FR-realestate-scraping$ cd realestate_scraper
(venv) softverse@Softverse:~/FR-realestate-scraping/realestate_scraper$ pytest
=================================================================== test session starts ====================================================================
platform linux -- Python 3.12.3, pytest-9.0.3, pluggy-1.6.0
rootdir: /home/softverse/FR-realestate-scraping/realestate_scraper
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.13.0, asyncio-1.3.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 111 items

tests/domain_loader.py ....                                                                                                                          [  3%]
tests/error_codes.py .......                                                                                                                         [  9%]
tests/extractor_pipeline.py ..                                                                                                                       [ 11%]
tests/fingerprint.py ....                                                                                                                            [ 15%]
tests/listing_filter.py .......                                                                                                                      [ 21%]
tests/resolvers/agent_name.py ...                                                                                                                    [ 24%]
tests/resolvers/bedrooms.py ...                                                                                                                      [ 27%]
tests/resolvers/coordinates.py ...                                                                                                                   [ 29%]
tests/resolvers/dpe.py ...                                                                                                                           [ 32%]
tests/resolvers/email.py ............                                                                                                                [ 43%]
tests/resolvers/location.py ......                                                                                                                   [ 48%]
tests/resolvers/phone.py ...                                                                                                                         [ 51%]
tests/resolvers/price.py .....                                                                                                                       [ 55%]
tests/resolvers/property_type.py ....                                                                                                                [ 59%]
tests/resolvers/reference.py .....                                                                                                                   [ 63%]
tests/resolvers/rooms.py ....                                                                                                                        [ 67%]
tests/resolvers/surface.py ....                                                                                                                      [ 71%]
tests/storage.py ........                                                                                                                            [ 78%]
tests/utils/geocoder.py .....                                                                                                                        [ 82%]
tests/utils/json_ld.py ...                                                                                                                           [ 85%]
tests/utils/text.py .........                                                                                                                        [ 93%]
tests/utils/url.py .......                                                                                                                           [100%]

=================================================================== 111 passed in 5.04s ====================================================================
(venv) softverse@Softverse:~/FR-realestate-scraping/realestate_scraper$ python -m scraper --reset-checkpoint
15:09:58 INFO    scraper.domain_loader | input loaded: 38 unique domains, 0 rows without website
15:09:58 INFO    scraper.pipeline | loaded 38 jobs (38 pending after checkpoint)
15:10:17 INFO    scraper.pipeline | start maxihome.net
15:10:17 INFO    scraper.pipeline | start maisonsoxygene.com
15:10:17 INFO    scraper.pipeline | start capwestresidence.fr
15:10:18 INFO    scraper.pipeline | start beausejour-immobilier.fr
15:10:21 INFO    scraper.pipeline | start rhpatrimoine.com
15:10:24 INFO    scraper.extractors.static_extractor | static: maxihome.net -> 2 candidate listing URLs
15:10:24 INFO    scraper.pipeline | start stephaneplazaimmobilier.com
15:10:25 INFO    scraper.extractors.static_extractor | static: no candidate listings for capwestresidence.fr
15:10:25 INFO    scraper.extractors.static_extractor | static: rhpatrimoine.com -> 80 candidate listing URLs
15:10:27 INFO    scraper.pipeline | start pietrapolis.fr
15:10:28 INFO    scraper.extractors.static_extractor | static: no candidate listings for maisonsoxygene.com
15:10:33 INFO    scraper.extractors.static_extractor | static: no candidate listings for pietrapolis.fr
15:10:40 INFO    scraper.pipeline | start zelidom.fr
15:10:41 INFO    scraper.extractors.dynamic_extractor | dynamic: no candidate listings for stephaneplazaimmobilier.com
15:10:41 INFO    scraper.pipeline | done stephaneplazaimmobilier.com status=failed listings=0 strategy=none reason=blocked_403 in 30.0s
15:10:41 INFO    scraper.extractors.dynamic_extractor | dynamic: maxihome.net -> 2 candidate listing URLs
15:10:41 INFO    scraper.pipeline | done rhpatrimoine.com status=success listings=5 strategy=static reason= in 30.9s
15:10:46 INFO    scraper.extractors.dynamic_extractor | dynamic: no candidate listings for capwestresidence.fr
15:10:46 INFO    scraper.pipeline | done maxihome.net status=failed listings=0 strategy=static reason=no_listings_found in 35.0s
15:10:46 INFO    scraper.pipeline | done capwestresidence.fr status=failed listings=0 strategy=static reason=no_listings_found in 35.0s
15:10:47 INFO    scraper.extractors.static_extractor | static: no candidate listings for zelidom.fr
15:10:51 INFO    scraper.extractors.dynamic_extractor | dynamic: pietrapolis.fr -> 1 candidate listing URLs
15:10:53 INFO    scraper.pipeline | start igor-immobilier.com
15:10:53 INFO    scraper.pipeline | start cosialis.fr
15:10:53 INFO    scraper.pipeline | start nestenn.com
15:10:58 INFO    scraper.pipeline | start agencealbert1er.fr
15:10:58 INFO    scraper.extractors.dynamic_extractor | dynamic: maisonsoxygene.com -> 14 candidate listing URLs
15:11:00 INFO    scraper.pipeline | done pietrapolis.fr status=failed listings=0 strategy=static reason=no_listings_found in 46.6s
15:11:02 INFO    scraper.extractors.static_extractor | static: no candidate listings for agencealbert1er.fr
15:11:05 INFO    scraper.extractors.static_extractor | static: nestenn.com -> 30 candidate listing URLs
15:11:12 INFO    scraper.pipeline | start carmen-immobilier.com
15:11:13 INFO    scraper.pipeline | done carmen-immobilier.com status=failed listings=0 strategy=none reason=site_not_reachable in 11.3s
15:11:13 INFO    scraper.extractors.static_extractor | static: cosialis.fr -> 80 candidate listing URLs
15:11:14 INFO    scraper.extractors.dynamic_extractor | dynamic: beausejour-immobilier.fr -> 80 candidate listing URLs
15:11:14 INFO    scraper.extractors.static_extractor | static: igor-immobilier.com -> 80 candidate listing URLs
15:11:17 INFO    scraper.extractors.dynamic_extractor | dynamic: agencealbert1er.fr -> 8 candidate listing URLs
15:11:18 INFO    scraper.pipeline | done nestenn.com status=success listings=21 strategy=static reason= in 34.5s
15:11:18 INFO    scraper.pipeline | start sporting-immobilier.fr
15:11:20 INFO    scraper.extractors.dynamic_extractor | dynamic: no candidate listings for zelidom.fr
15:11:20 INFO    scraper.pipeline | done zelidom.fr status=failed listings=0 strategy=static reason=no_listings_found in 66.2s
15:11:21 INFO    scraper.pipeline | done maisonsoxygene.com status=failed listings=0 strategy=static reason=no_listings_found in 67.2s
15:11:29 INFO    scraper.pipeline | done beausejour-immobilier.fr status=success listings=3 strategy=dynamic reason= in 72.0s
15:11:29 INFO    scraper.pipeline | start agencegrossi.com
15:11:29 INFO    scraper.pipeline | start agencedeneuville.com
15:11:32 INFO    scraper.pipeline | start mg-immobilier.com
15:11:34 INFO    scraper.extractors.static_extractor | static: sporting-immobilier.fr -> 80 candidate listing URLs
15:11:34 INFO    scraper.extractors.static_extractor | static: no candidate listings for mg-immobilier.com
15:11:35 INFO    scraper.pipeline | start well-estate.fr
^C^C^C^C^C^C15:17:04 WARNING scraper.pipeline | domain mg-immobilier.com timed out after 316.6s
15:17:04 WARNING scraper.pipeline | domain agencealbert1er.fr timed out after 350.2s
15:17:04 INFO    scraper.pipeline | done mg-immobilier.com status=failed listings=0 strategy=none reason=no_listings_found in 316.6s
15:17:04 WARNING scraper.pipeline | domain cosialis.fr timed out after 346.1s
15:17:04 WARNING scraper.pipeline | domain igor-immobilier.com timed out after 346.1s
15:17:04 WARNING scraper.pipeline | domain sporting-immobilier.fr timed out after 322.1s
15:17:04 WARNING scraper.pipeline | domain agencegrossi.com timed out after 314.0s
15:17:04 INFO    scraper.pipeline | done agencealbert1er.fr status=failed listings=0 strategy=none reason=no_listings_found in 350.2s
15:17:04 INFO    scraper.pipeline | done cosialis.fr status=failed listings=0 strategy=none reason=no_listings_found in 346.1s
15:17:04 WARNING scraper.pipeline | domain agencedeneuville.com timed out after 315.0s
15:17:05 INFO    scraper.pipeline | done igor-immobilier.com status=failed listings=0 strategy=none reason=no_listings_found in 346.1s
15:17:05 INFO    scraper.pipeline | done sporting-immobilier.fr status=failed listings=0 strategy=none reason=no_listings_found in 322.1s
15:17:05 WARNING scraper.pipeline | domain well-estate.fr timed out after 310.2s
15:17:06 INFO    scraper.pipeline | done agencegrossi.com status=failed listings=0 strategy=none reason=no_listings_found in 314.0s
15:17:07 INFO    scraper.pipeline | start wretmanestate.com
15:17:08 INFO    scraper.pipeline | done agencedeneuville.com status=failed listings=0 strategy=none reason=site_not_reachable in 315.0s
15:17:08 INFO    scraper.pipeline | done well-estate.fr status=failed listings=0 strategy=none reason=no_listings_found in 310.2s
15:17:09 INFO    scraper.pipeline | done wretmanestate.com status=failed listings=0 strategy=none reason=site_not_reachable in 2.3s
15:17:09 INFO    scraper.pipeline | start agencecoullaud.fr
15:17:10 INFO    scraper.pipeline | start erapontdelarc.com
15:17:13 INFO    scraper.pipeline | start erafrance.com
15:17:13 INFO    scraper.pipeline | start aio-immobiliere.com
15:17:14 INFO    scraper.pipeline | start 2m-immo.com
15:17:14 INFO    scraper.pipeline | start novilis.fr
15:17:19 INFO    scraper.extractors.static_extractor | static: agencecoullaud.fr -> 54 candidate listing URLs
15:17:19 INFO    scraper.pipeline | start groupecif.com
15:17:20 INFO    scraper.extractors.static_extractor | static: no candidate listings for novilis.fr
15:17:20 INFO    scraper.extractors.dynamic_extractor | dynamic: no candidate listings for erapontdelarc.com
15:17:20 INFO    scraper.pipeline | done erapontdelarc.com status=failed listings=0 strategy=none reason=blocked_403 in 12.9s
15:17:22 INFO    scraper.extractors.static_extractor | static: no candidate listings for aio-immobiliere.com
15:17:22 INFO    scraper.pipeline | start agencemathieu.fr
15:17:25 INFO    scraper.extractors.dynamic_extractor | dynamic: no candidate listings for novilis.fr
15:17:25 INFO    scraper.pipeline | done novilis.fr status=failed listings=0 strategy=static reason=no_listings_found in 14.0s
15:17:30 INFO    scraper.pipeline | start agencedesflots.com
15:17:31 INFO    scraper.extractors.dynamic_extractor | dynamic: no candidate listings for aio-immobiliere.com
15:17:31 INFO    scraper.pipeline | done aio-immobiliere.com status=failed listings=0 strategy=static reason=no_listings_found in 22.0s
15:17:33 INFO    scraper.pipeline | start immoso.fr
15:17:33 INFO    scraper.extractors.static_extractor | static: no candidate listings for erafrance.com
15:17:34 INFO    scraper.pipeline | start vancia-immobilier.fr
15:17:34 INFO    scraper.extractors.static_extractor | static: groupecif.com -> 80 candidate listing URLs
15:17:35 INFO    scraper.extractors.static_extractor | static: 2m-immo.com -> 80 candidate listing URLs
15:17:36 INFO    scraper.extractors.static_extractor | static: agencemathieu.fr -> 44 candidate listing URLs
15:17:39 INFO    scraper.pipeline | done agencecoullaud.fr status=success listings=45 strategy=static reason= in 30.9s
15:17:41 INFO    scraper.extractors.static_extractor | static: immoso.fr -> 35 candidate listing URLs
15:17:41 INFO    scraper.extractors.static_extractor | static: no candidate listings for vancia-immobilier.fr
15:17:42 INFO    scraper.extractors.static_extractor | static: agencedesflots.com -> 80 candidate listing URLs
15:17:43 INFO    scraper.pipeline | start lgo-immobilier.fr
15:17:48 INFO    scraper.extractors.dynamic_extractor | dynamic: no candidate listings for erafrance.com
15:17:48 INFO    scraper.pipeline | done erafrance.com status=failed listings=0 strategy=static reason=no_listings_found in 40.8s
15:17:53 INFO    scraper.extractors.dynamic_extractor | dynamic: no candidate listings for vancia-immobilier.fr
15:17:53 INFO    scraper.pipeline | done vancia-immobilier.fr status=failed listings=0 strategy=static reason=no_listings_found in 18.8s
15:17:55 INFO    scraper.pipeline | start grisel-immobilier.fr
15:17:55 INFO    scraper.extractors.static_extractor | static: lgo-immobilier.fr -> 20 candidate listing URLs
15:17:57 INFO    scraper.pipeline | start groupimmo.pro
15:17:58 INFO    scraper.extractors.static_extractor | static: groupimmo.pro -> 80 candidate listing URLs
15:17:59 INFO    scraper.extractors.static_extractor | static: grisel-immobilier.fr -> 70 candidate listing URLs
15:18:08 INFO    scraper.pipeline | done groupecif.com status=success listings=48 strategy=static reason= in 57.6s
15:18:10 INFO    scraper.pipeline | start immobiliere-de-croix.com
15:18:12 INFO    scraper.extractors.static_extractor | static: no candidate listings for immobiliere-de-croix.com
15:18:13 INFO    scraper.extractors.dynamic_extractor | dynamic: no candidate listings for immobiliere-de-croix.com
15:18:13 INFO    scraper.pipeline | done immobiliere-de-croix.com status=failed listings=0 strategy=static reason=no_listings_found in 5.2s
15:18:22 INFO    scraper.pipeline | start imbs-immo.com
15:18:23 INFO    scraper.pipeline | done 2m-immo.com status=success listings=79 strategy=static reason= in 68.8s
15:18:24 INFO    scraper.extractors.static_extractor | static: imbs-immo.com -> 80 candidate listing URLs
15:18:29 INFO    scraper.pipeline | start tit-immobilier.com
15:18:29 INFO    scraper.pipeline | done agencemathieu.fr status=success listings=35 strategy=static reason= in 63.2s
15:18:32 INFO    scraper.extractors.static_extractor | static: tit-immobilier.com -> 22 candidate listing URLs
15:18:33 INFO    scraper.pipeline | start jeminstalleici.com
15:18:34 INFO    scraper.extractors.static_extractor | static: no candidate listings for jeminstalleici.com
15:18:34 INFO    scraper.extractors.dynamic_extractor | dynamic: no candidate listings for jeminstalleici.com
15:18:34 INFO    scraper.pipeline | done jeminstalleici.com status=failed listings=0 strategy=static reason=no_listings_found in 5.3s
15:18:35 INFO    scraper.pipeline | done immoso.fr status=success listings=33 strategy=static reason= in 63.8s
15:18:40 INFO    scraper.pipeline | start piriac-immobilier.fr
15:18:46 INFO    scraper.extractors.static_extractor | static: piriac-immobilier.fr -> 63 candidate listing URLs
15:18:54 INFO    scraper.extractors.static_extractor | static: agencedesflots.com gather budget exhausted after 66.0s, keeping 5 listings
15:18:54 INFO    scraper.pipeline | done agencedesflots.com status=success listings=5 strategy=static reason= in 96.0s
15:19:05 INFO    scraper.pipeline | done groupimmo.pro status=success listings=10 strategy=static reason= in 68.7s
15:19:05 INFO    scraper.pipeline | done lgo-immobilier.fr status=success listings=8 strategy=static reason= in 77.5s
15:19:11 INFO    scraper.extractors.static_extractor | static: grisel-immobilier.fr gather budget exhausted after 66.0s, keeping 23 listings
15:19:11 INFO    scraper.pipeline | done grisel-immobilier.fr status=success listings=23 strategy=static reason= in 72.6s
15:19:20 INFO    scraper.pipeline | done imbs-immo.com status=success listings=12 strategy=static reason= in 61.8s
15:19:24 INFO    scraper.pipeline | done tit-immobilier.com status=success listings=20 strategy=static reason= in 55.7s
15:19:46 INFO    scraper.pipeline | done piriac-immobilier.fr status=success listings=63 strategy=static reason= in 65.8s
15:19:46 INFO    scraper.pipeline | finished: 410 listings written
15:19:46 INFO    scraper.report | report written: /home/softverse/FR-realestate-scraping/realestate_scraper/output/scrape_report.md
15:19:46 ERROR   asyncio | Future exception was never retrieved
future: <Future finished exception=TargetClosedError('Target page, context or browser has been closed')>
playwright._impl._errors.TargetClosedError: Target page, context or browser has been closed
(venv) softverse@Softverse:~/FR-realestate-scraping/realestate_scraper$
