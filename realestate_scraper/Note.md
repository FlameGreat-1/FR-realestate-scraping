
YOU HAVE FULL AND COMPLETE READ AND WRITE ACCESS TO THE REPO FROM MY OTHER ACCOUNT BECAUSE I HAVE ADDED YOU AS A GROUP MEMEBER WITH A DEVELOPER ROLE:
https://gitlab.com/scrap-group/scrap-project
SO IT MEANS YOU CAN EXAMINE FILES, MODIFY, CREATE AND IMPLEMENT, COMMIT AND CREATE MERGE REQUEST ETC
CRITICAL: EVERYTHING IS ON THE MAIN BRANCH. 
DO NOT FOOLSIHLY START LISTING WHAT IS ON THE MASTER BRANCH
HERE IS EXACTLY WHAT I WANT YOU TO DO:
OW WE ARE GOING TO WORK ON THIS TEST GIVEN TO ME.
THE CURRENT CODEBASE IS EXACTLY WHAT I HAVE DONE
THERE ARE OVER 200+ PARTICIPANT AND MY GOAL TO ACHIEVE 1ST POSITION AND NOTHING LESS THAN 1ST POSITION.
SO AS A SENIOR BACKEND ENGINEER WITH CCOMBINED EXPERTISE ON SCRAPING, AUTOMATION, OPTIMIZATION, CODE QUALITY, SCALABILITY ETC YOU ARE GOING TO WORK WITH ME TO ACHIEVE THIS .

REQUIREMENTS AND INSTRUCTIONS GIVEN IS AT THE /rules/

DATA GIVEN ONLY IS AT THE /data/. 

I RAN A SMOKE TEST FOR 3 DOMAINS AND THE RESULT IS AT THE /outputs/



softverse@Softverse:~/FR-realestate-scraping$ cd realestate_scraper
softverse@Softverse:~/FR-realestate-scraping/realestate_scraper$ ls
Note.md  README.md  data  docs  output  pytest.ini  requirements.txt  roles  rules  run_production.py  run_scraper.py  scraper  tests  venv
softverse@Softverse:~/FR-realestate-scraping/realestate_scraper$ source venv/bin/activate
(venv) softverse@Softverse:~/FR-realestate-scraping/realestate_scraper$ python -m scraper --limit 3 --reset-checkpoint
00:30:02 INFO    scraper.domain_loader | input loaded: 38 unique domains, 0 rows without website
00:30:02 INFO    scraper.pipeline | loaded 38 jobs (38 pending after checkpoint)
00:30:03 INFO    scraper.pipeline | start beausejour-immobilier.fr
00:30:03 INFO    scraper.pipeline | start rhpatrimoine.com
00:30:03 INFO    scraper.pipeline | start maxihome.net
00:30:05 INFO    scraper.pipeline | done rhpatrimoine.com status=failed listings=0 strategy=none reason=site_not_reachable in 1.9s
00:30:26 INFO    scraper.extractors.dynamic_extractor | dynamic: no candidate listings for beausejour-immobilier.fr
00:30:35 INFO    scraper.extractors.static_extractor | static: maxihome.net -> 120 candidate listing URLs
00:31:11 INFO    scraper.pipeline | done maxihome.net status=success listings=90 strategy=static reason= in 68.0s
00:33:03 INFO    scraper.extractors.static_extractor | static: beausejour-immobilier.fr -> 120 candidate listing URLs
00:35:26 INFO    scraper.pipeline | done beausejour-immobilier.fr status=success listings=60 strategy=static reason= in 323.5s
00:35:26 INFO    scraper.pipeline | finished: 150 listings written
(venv) softverse@Softverse:~/FR-realestate-scraping/realestate_scraper$
(venv) softverse@Softverse:~/FR-realestate-scraping/realestate_



EXAMINE THE ENTIRE CODEBASE DEEPLY AND THOROUGHLY.


YOU MUST DEPLOY ALL POSSIBLE AND AVAILABLE EXPERTISE AS A SENIOR ENGINEER TO ENSURE WE EXECUTE THIS WITH 100% PRECISION AND ACCURACY AND COME UP NUMBER 1 NOTHING LESS.
YOU MUST AVOID GUESSING
AVOID ASSUMPTIONS
THIS IS VERY CRITICAL AND MUST BE TACKLED HEAD-ON
WE MUST ACHIEVE ALL OF THESE WITH PRECISION:
Important Context
This is part of a large-scale project (55k+ domains)
Focus is on:
Scalability
Speed (runtime optimization)
Data quality
Many sites share similar structures → reuse logic where possible
Do NOT treat each site manually one-by-one
Key Expectations
Handle multiple sites efficiently
Avoid scraping one site at a time manually
Reuse patterns across similar websites
Optimize runtime (current bottleneck)
Ensure clean and consistent data
Avoid invalid pages (CSS, homepage, non-listing pages)
Deduplicate listings per site
Evaluation Criteria
We will evaluate based on:
Code quality and structure
Runtime performance
Data accuracy and completeness
Handling of edge cases
Scalability of solution

YOU MUST MAKE SURE  YOU APPLY BEST ENGINEERING BEST PRACTICES, ENTERPRISE GRADE, PRODUCTION GRADE AND INDUSTRY STANDARD.
EVERYTHING MUST BE COMPLETE, ACCURATE AND WORKING PERFECTLY END TO END 
EVERYTHING MUST BE CLEAN, SCALABLE , MAINTAINABLE ETC.
AVOID HARDCODING THINGS, AVOID REDUDANCIES, AVOID DUPLICATES, AVOID WRONG USAGE, AVOID PLACEHOLDERS ETC.
DO YOU REALLY UNDERSTAND EVERYTHING I HAVE INSTRUCTED ?
SO EXAMINE ALL AS I HAVE INSTRUCTED  AND LET ME KNOW BEFORE WE PROCEED


SO WHAT DO YOU THINK BEFORE I RUN THE FULL PIPELINE?









I HOPE YOU KNOW THAT I SAID THIS FILES IS FROM THEIR OWN ORIGINAL CODEBASE:  output/scrape_report.md, realestate_scraping_report.md, error_log.csv ??
SO YOU HAVE TO START NOW EXECUTING THE 13 THINGS AND MANY MORE.
REMEMBER WE ARE TALKING REAL ENGINEERING HERE AND A SENIOR ENGINEER YOU MUST EXECUTE WITH 100% PRECISION AND ACCURACY. ENSURE EVERYTHING IS COMPLETE, ACCURATE AND WORKING PERFECTLY.
STRICTLY ENSURE YOU FOLLOW BEST ENGINEERING PRACTICES, ENTERPRISE GRADE AND INDUSTRY STANDARD.
AVOID GUESSING
AVOID ASSUMPTIONS
YOU MUST BE 100% CERTAIN AND SURE OF EVERYTHING
PLEASE: WE MUST GET THE EXACT REQUIREMENTS THEY ARE LOOKING FOR 100% TO COME UP NUMBER 1
SO YOU MUST TAKE THIS SERIOUSLY
ENSURE CLEAN, MAINTAINABLE, SCALABLE CODES. 
AVOID DEAD CODES, REDUNDANCIES, REPETITIONS, HARDCODING, PLACEHOLDERS ETC
SINCE THIS IS VERY BIG, YOU SHOULD COMMIT IT IN VARIOUS PHASES.
AVOID COMMITINING TOO MANY FILES AT SAME TIME TO ENSURE YOU CAREFULLY DESIGN AND ENGINEER EVERYTHING PROPERLY
LASTLY, YOU SHOULD COMMIT DIRECTLY TO THE MAIN BRANCH VIA TGE URL
I HOPE YOU UNDERSTAND CLEARLY EVERYTHING I SAID?






python -m scraper