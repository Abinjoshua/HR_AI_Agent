from flask import Flask, request, render_template, redirect, url_for, session
import PyPDF2
from docx import Document
from io import BytesIO
from sentence_transformers import SentenceTransformer
import numpy as np
from google_calendar import get_calendar_service, schedule_interview
import datetime
import re
import os
import logging

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management

logging.basicConfig(level=logging.INFO)

# Correct model name
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')


def extract_text_from_pdf(file_bytes):
    reader = PyPDF2.PdfReader(BytesIO(file_bytes))
    text = ''
    for page in reader.pages:
        text += page.extract_text() or ''
    return text


def extract_text_from_docx(file_bytes):
    doc = Document(BytesIO(file_bytes))
    text = '\n'.join(para.text for para in doc.paragraphs)
    return text


def parse_resume(file):
    file_bytes = file.read()
    filename = file.filename.lower()
    if filename.endswith('.pdf'):
        return extract_text_from_pdf(file_bytes)
    elif filename.endswith('.docx'):
        return extract_text_from_docx(file_bytes)
    else:
        return None


def get_embedding(text):
    embedding = model.encode(text)
    return embedding.tolist()


def cosine_similarity(vec1, vec2):
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    if np.linalg.norm(vec1) == 0 or np.linalg.norm(vec2) == 0:
        return 0.0
    return float(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))


def extract_email_and_name(text):
    email_match = re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text)
    email = email_match.group(0) if email_match else None

    name = None
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if lines:
        first_line_words = lines[0].split()
        name = ' '.join(first_line_words[:2]) if len(first_line_words) >= 2 else lines[0]

    return email, name


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'upload_analyze' in request.form:
            job_description = request.form['job_description']
            resumes = request.files.getlist('resumes')

            parsed_resumes = []
            candidate_info = {}

            for resume in resumes:
                text = parse_resume(resume)
                if text:
                    email, name = extract_email_and_name(text)
                else:
                    email, name = None, None
                parsed_resumes.append({'filename': resume.filename, 'content': text})
                candidate_info[resume.filename] = {'email': email, 'name': name}

            job_emb = get_embedding(job_description)

            ranked_candidates = []
            for candidate in parsed_resumes:
                content = candidate['content']
                score = cosine_similarity(job_emb, get_embedding(content[:4000])) if content else 0.0
                ranked_candidates.append({
                    'filename': candidate['filename'],
                    'score': score,
                    'summary': content[:700] if content else 'No content extracted'
                })

            ranked_candidates.sort(key=lambda x: x['score'], reverse=True)

            session['job_description'] = job_description
            session['ranked_candidates'] = ranked_candidates
            session['candidate_info'] = candidate_info

            return render_template('index.html', ranked_candidates=ranked_candidates, job_description=job_description)

        elif 'confirm_selection' in request.form:
            selected_filenames = request.form.getlist('selected_candidates')
            service = get_calendar_service()

            candidate_info = session.get('candidate_info', {})

            start_time = datetime.datetime.now() + datetime.timedelta(days=1)
            start_time = start_time.replace(hour=9, minute=0, second=0, microsecond=0)
            end_time = start_time + datetime.timedelta(minutes=30)

            scheduled_links = []

            for filename in selected_filenames:
                info = candidate_info.get(filename)
                if info and info.get('email'):
                    candidate_name = info.get('name', filename)
                    try:
                        link = schedule_interview(service, info['email'], candidate_name, start_time, end_time)
                        if link:
                            logging.info(f"Interview scheduled successfully for {candidate_name} ({info['email']})")
                            scheduled_links.append({'candidate': candidate_name, 'link': link})
                        else:
                            logging.error(f"Failed to schedule event for {candidate_name} ({info['email']}) - No link returned")
                            scheduled_links.append({'candidate': candidate_name, 'link': 'Failed to schedule event'})
                    except Exception as e:
                        logging.error(f"Exception while scheduling interview for {candidate_name} ({info['email']}): {str(e)}")
                        scheduled_links.append({'candidate': candidate_name, 'link': 'Failed to schedule event'})
                else:
                    logging.warning(f"No valid email found for candidate file: {filename}")
                    scheduled_links.append({'candidate': filename, 'link': 'No email found'})

            return render_template('schedule_confirmation.html', scheduled_links=scheduled_links)

        # Fallback for unknown POST forms:
        return redirect(url_for('index'))

    # GET handling
    ranked_candidates = session.get('ranked_candidates')
    job_description = session.get('job_description')
    return render_template('index.html', ranked_candidates=ranked_candidates, job_description=job_description)


if __name__ == '__main__':
    app.run(debug=True)
