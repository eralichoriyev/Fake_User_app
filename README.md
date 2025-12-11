

SQL Fake User Data Generator (“Faker in SQL”)


Overview
This project implements a deterministic fake user data generator using MySQL stored routines.
The goal is to have a “Faker-like” library implemented directly in SQL and consumed by a Python Flask web application.

All randomness is implemented in SQL.
The Python layer is only responsible for:

   calling stored procedures,
   passing parameters (locale, seed, batch index, batch size),
   and rendering HTML.

Database Schema

locales

Stores supported locales (regions / languages).
    <img width="671" height="193" alt="image" src="https://github.com/user-attachments/assets/f451d597-8e88-465f-97f3-eefa5a4cc556" />


Example rows:
    en_US – English / United States
    de_DE – German / Germany
    pl_PL – Polish / Poland (can be added)
    etc.

Used by other tables via locale_id.
name_parts
Extensible table for all name-related building blocks.
   <img width="706" height="290" alt="image" src="https://github.com/user-attachments/assets/04d0c3d2-1905-4061-85cb-c0c4d2f8e777" />

part_type controls whether this row is title, first name, middle name, or last name
locale_id links to locales
gender can be used to customize distributions
popularity_weight allows non-uniform sampling (e.g. “Smith” more common than “Brown”)

This satisfies the requirement of a single table instead of english_names, german_names, etc.

address_parts (extensible, optional usage)
       <img width="881" height="340" alt="image" src="https://github.com/user-attachments/assets/e6927298-4890-481a-94a9-8e0ce5beeffb" />

This table is designed to generate locale-specific addresses using:
    components (street_name, street_suffix, city, …),
    and pattern templates (e.g. {street_number} {street_name} {street_suffix}, {city}).

Note: in the current implementation, address generation can be added on top of the existing pattern using the same seeded-random approach as for names.

Stored Routines (“Library API”)
1. seeded_rand – deterministic uniform random generator
Signature:
   <img width="1078" height="660" alt="image" src="https://github.com/user-attachments/assets/ba8e5365-9167-42cb-b161-1ef4ae9394e0" />

Purpose:
Deterministic pseudo-random number generator that returns a uniform value in [0, 1).
It is purely functional: for the same parameters, it always returns the same result. This guarantees reproducibility across runs.

Algorithm:
    Concatenate all inputs: seed, batch_idx, row_idx, salt
    Compute SHA-256: SHA2(CONCAT(...), 256)
    Take a substring of the hex digest
    Convert hex → decimal using CONV
    Normalize to [0, 1) by dividing with a large constant.
Pseudo-code:
 <img width="731" height="249" alt="image" src="https://github.com/user-attachments/assets/07a8600d-7cc7-4aea-b7d2-b15a56178300" />

Usage:
    seed – user-provided seed (ensures reproducibility)
    batch_idx – which batch (page) we are generating (0, 1, 2, …)
    row_idx – index of user within the batch
    salt – simple integer “channel id” to get different random values for different attributes
Because it is based on a hash, the output is:
    uniform in [0, 1),
    deterministic,
    independent between different salts.
2. generate_fake_user – generate a single user (core logic)
Signature:
    <<img width="227" height="127" alt="image" src="https://github.com/user-attachments/assets/5efd7fac-c41f-4f4c-a1ab-4477b5b599f1" />

Arguments:
    p_locale_id – which locale’s data to use (locales.id)
    p_seed – user-provided seed
    p_batch_idx – batch index (for pagination)
    p_row_idx – index of this user in batch
Output:
Returns a single result row with:
    full_name
    latitude
    longitude
    height_cm
    weight_kg
    phone
    email
(Addresses can be integrated later using address_parts.)
Implemented logic:
Title / First / Middle / Last name
    Uses name_parts with part_type = 'title' | 'first' | 'middle' | 'last'
    Ordering is randomized using seeded_rand(...) in the ORDER BY clause
    Title appears with 50% probability
    Middle name appears with 30% probability
    Names are concatenated using CONCAT_WS and TRIM


<img width="567" height="131" alt="image" src="https://github.com/user-attachments/assets/242c161c-feb9-488c-b140-b08d194552de" />


Geolocation – uniform on the sphere
To get a uniform distribution on a sphere:
Generate u, v ~ U(0, 1) using seeded_rand
Compute latitude and longitude as:

<!-- latitude  = asin(2u - 1)   (converted to degrees)
longitude = 360v - 180 -->

In SQL:

<img width="527" height="117" alt="image" src="https://github.com/user-attachments/assets/5ea25478-40e8-4f31-b6f9-2aa2f8ede0ba" />


This ensures the probability density is constant over the sphere, not clustered towards the poles.
Physical attributes – normal distribution (Box–Muller)
To generate a standard normal variable Z ~ N(0, 1), the Box–Muller transform is used:

<!-- Z = sqrt(-2 ln(U1)) * cos(2π U2) -->

where U1, U2 ~ U(0, 1). To avoid numerical issues (ln(0)), values are clamped into (0,1).
In SQL:

<img width="586" height="152" alt="image" src="https://github.com/user-attachments/assets/cb9303f3-836a-4b41-9df7-e6080b33bff1" />


Then height and weight are computed as affine transforms:

<img width="413" height="65" alt="image" src="https://github.com/user-attachments/assets/f4587a1b-0d0a-46d4-98fa-3be935940111" />


Phone number – Polish format
Phone numbers are generated deterministically in Polish format:
<!-- 
+48 ABC DEF GHI -->

where ABC, DEF, GHI are pseudo-random numeric blocks:

<img width="633" height="159" alt="image" src="https://github.com/user-attachments/assets/53853163-3505-4769-a8c3-b1968bd4bf78" />


+48 is the Polish country code
Sufficiently realistic for demonstration purposes
Email
E-mail addresses are built from the chosen first/last name + random number:


<img width="634" height="156" alt="image" src="https://github.com/user-attachments/assets/0d13403a-7f65-4166-82da-b8e86f81f811" />


3. generate_fake_user_batch – generate a batch of users
Signature:

<img width="679" height="203" alt="image" src="https://github.com/user-attachments/assets/789f2416-8732-496f-af36-4f4839f68b20" />

Arguments:
p_locale_id – locale
p_seed – seed
p_batch_idx – batch/page number
p_batch_size – how many users to generate at once (e.g. 10)
Behavior:
Creates a temporary table tmp_users:

<img width="529" height="225" alt="image" src="https://github.com/user-attachments/assets/c352b4a2-0df2-4a97-ac2c-f04d483fab7f" />


Loops from i = 0 to p_batch_size - 1:
For each i, repeats the same logic as generate_fake_user:
names
geo
physical attributes
phone
email
Inserts a row into tmp_users
Returns the content of tmp_users:


(  SELECT * FROM tmp_users; )


Determinism and reproducibility:

 For fixed (p_locale_id, p_seed, p_batch_idx, p_batch_size), the output rows are always identical.

 Changing p_batch_idx (0, 1, 2, …) gives non-overlapping deterministic batches (“next page of users”).
 Example usage:


CALL generate_fake_user_batch(1, 12345, 0, 10);  -- first 10 users, locale 1
CALL generate_fake_user_batch(1, 12345, 1, 10);  -- next 10 users -->


Flask Integration (How the library is used)
The Flask app connects to MySQL and treats the stored procedures as a backend faker API.
Key points:
User selects:
    locale_id
    seed
    batch
Flask calls:



<!-- cursor.callproc(
    "generate_fake_user_batch",
    [locale_id, seed, batch, batch_size]
)

for result in cursor.stored_results():
    users = result.fetchall() -->



The result set is rendered in an HTML table.

Benchmarking (users/second)

To measure performance, we can:
1. Call generate_fake_user_batch with a large p_batch_size (e.g. 10,000)
2. Measure the time in Python using time.time() before/after the call
3. Compute:


<!-- users_per_second = total_users_generated / elapsed_time_seconds -->


Example concept (Python):


<!-- import time

start = time.time()
cursor.callproc("generate_fake_user_batch", [1, 12345, 0, 10000])
for result in cursor.stored_results():
    rows = result.fetchall()
elapsed = time.time() - start
print("Generated", len(rows), "users in", elapsed, "seconds")
print("Users per second:", len(rows) / elapsed) -->

You can run this once, record the numbers, and include them in the submission.


Summary
    Randomness implemented entirely in SQL (seeded_rand + math functions).
    Stored procedures form a reusable faker library:
        seeded_rand
        generate_fake_user
        generate_fake_user_batch
    Output depends deterministically on:
        locale
        seed
        batch index
        index within batch
Flask app is just a UI wrapper around the SQL faker.
