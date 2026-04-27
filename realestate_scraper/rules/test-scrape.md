**Sheba-X – Web Scraping Test Task (Real Estate)**

**Overview**  
 This is a test task to evaluate your approach to building or improving a scalable web scraping system.

You are given a CSV containing **\~50 real estate agency websites (domains)**.  
 Your goal is to extract **property listings data** from these sites in a structured and reliable way.

---

**Important Context**

* This is part of a **large-scale project (55k+ domains)**  
* Focus is on:  
  * **Scalability**  
  * **Speed (runtime optimization)**  
  * **Data quality**  
* Many sites share similar structures → reuse logic where possible  
* Do NOT treat each site manually one-by-one

---

**Your Task**

Build or improve a scraper that:

1. Takes a CSV of domains as input  
2. Visits each website  
3. Extracts property listings  
4. Outputs structured data

---

**Output Requirements**

### **1\. Listings CSV**

One row per property listing

Required fields:

* reference\_id  
* price  
* property\_type  
* location  
* surface\_area  
* rooms  
* bedrooms  
* agency\_name  
* agent\_name  
* phone\_number  
* email  
* coordinates  
* dpe\_rating  
* source\_url  
* source\_domain

---

### **2\. Error Log CSV**

For any domain that fails or has no listings:

* domain  
* status  
* reason

Example reasons:

* no\_website  
* no\_listings\_found  
* site\_not\_reachable  
* blocked\_403  
* dynamic\_js\_required  
* parsing\_failed

---

**Approach Options**

You can choose one:

**Option 1:** Build your own solution from scratch  
 **Option 2:** Improve/refactor existing code (focus on speed \+ accuracy)

---

**Key Expectations**

* Handle multiple sites efficiently  
* Avoid scraping one site at a time manually  
* Reuse patterns across similar websites  
* Optimize runtime (current bottleneck)  
* Ensure clean and consistent data  
* Avoid invalid pages (CSS, homepage, non-listing pages)  
* Deduplicate listings per site

---

**Evaluation Criteria**

We will evaluate based on:

* Code quality and structure  
* Runtime performance  
* Data accuracy and completeness  
* Handling of edge cases  
* Scalability of solution

---

**Goal**

We are not expecting perfection.

We are looking for:

* A **solid approach**  
* Good **engineering decisions**  
* Ability to **scale this to thousands of sites**

---

**Next Step**

If your solution is strong, we will continue with:

* Larger datasets  
* Ongoing part-time collaboration on this and other projects.

