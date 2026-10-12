from pprint import pprint
from db import show_schema, get_patient_context, store_session
 
PATIENT_ID = 1 
 
show_schema()
 
print("\n--- context ---")
pprint(get_patient_context(PATIENT_ID))
 

 