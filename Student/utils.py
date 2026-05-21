
#this function checks if student profile complete or not
def update_profile_status(student):

    personal = getattr(student, 'personal_detail', None)
    education = getattr(student, 'education', None)
    career = getattr(student, 'career_preference', None)

    if not (personal and education and career):
        student.profile_completed = False
        student.save(update_fields=['profile_completed'])
        return

    is_complete = all([

        # Personal Details
        personal.first_name,
        personal.last_name,
        personal.email,
        personal.whatsapp_no,
        personal.birthplace_state,
        personal.date_of_birth,
        personal.gender,
        personal.permanent_state,
        personal.permanent_city,
        personal.permanent_pin_code,
        personal.permanent_address,
        personal.current_state,
        personal.current_city,
        personal.current_pin_code,
        personal.current_address,

        # Education
        education.qualification,
        education.specialization,
        education.college_name,
        education.college_state,
        education.passing_year,
        education.cgpa,
        education.skills,   

        #Career Preference
        career.preferred_job_role,
        career.work_mode,
        career.preferred_time,
        career.experience,
        career.expected_ctc
    ])

    # Update only if changed 
    if student.profile_completed != is_complete:
        student.profile_completed = is_complete
        student.save(update_fields=['profile_completed'])