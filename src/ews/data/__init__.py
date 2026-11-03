"""ews.data — synthetic data generation (Stage 2).

WHAT:  Modules that create the fictitious CSME loan book, one table family each:
           customers.py   relationship_managers + customers   (Lesson 6)
           (more modules are added in Lessons 7–10)
WHY:   Keeping generation logic in the package (not in a notebook) means the
       data can be rebuilt identically by one command: python scripts/generate_data.py
"""