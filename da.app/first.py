import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
import os
import ftplib
import mysql.connector
from mysql.connector import errorcode

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("my_fastapi")

app = FastAPI()

# CORS 설정
origins = [
    "http://localhost/submission",
    "http://127.0.0.1:8000/submission",
    "http://your-frontend-domain.com",
    "http://127.0.0.1:5500",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 로깅 미들웨어
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"Response: {response.status_code}")
    return response

# 루트 핸들러 정의
@app.get("/")
async def root():
    return {"message": "Hello World"}

def get_db():
    try:
        cnx = mysql.connector.connect(user='youruser', password='yourpassword',
                                      host='yourhost',
                                      database='yourdatabase')
        return cnx
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            logger.error("아이디 혹은 비밀번호가 틀렸습니다.")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            logger.error("존재하지 않는 계정입니다.")
        else:
            logger.error(err)
        return None

class Submission(BaseModel):
    username: str
    code: str

class UpdateStatus(BaseModel):
    id: int
    status: str

class ExecutionResult(BaseModel):
    id: int
    username: str
    password: str

@app.post("/submission")
async def submit_code(submission: Submission):
    cnx = get_db()
    if not cnx:
        raise HTTPException(status_code=500, detail="데이터베이스에 연결하지 못했습니다.")
    
    cursor = cnx.cursor()
    add_submission = ("INSERT INTO submissions "
                      "(username, status, created_at, updated_at, code) "
                      "VALUES (%s, %s, %s, %s, %s)")
    timestamp = datetime.utcnow()
    data_submission = (submission.username, 'SUBMITTED', timestamp, timestamp, submission.code)

    cursor.execute(add_submission, data_submission)
    submission_id = cursor.lastrowid
    cnx.commit()

    submission_dir = "./submission_dir"
    if not os.path.exists(submission_dir):
        os.makedirs(submission_dir)
    
    file_path = os.path.join(submission_dir, f"{submission_id}.py")
    with open(file_path, 'w') as f:
        f.write(submission.code)

    cursor.close()
    cnx.close()

    logger.info(f"Submission received: {submission_id}")

    return {"reservation_number": submission_id}

@app.get("/new")
async def process_submission():
    cnx = get_db()
    if not cnx:
        raise HTTPException(status_code=500, detail="데이터베이스에 연결하지 못했습니다.")

    cursor = cnx.cursor(dictionary=True)
    query = ("SELECT id, code FROM submissions WHERE status = 'SUBMITTED' "
             "ORDER BY created_at ASC LIMIT 1")
    cursor.execute(query)
    submission = cursor.fetchone()

    if not submission:
        cursor.close()
        cnx.close()
        return {"detail": "No submissions found"}

    file_path = f"./submission_dir/{submission['id']}.py"
    with open(file_path, 'w') as f:
        f.write(submission['code'])

    try:
        ftp = ftplib.FTP('ftp.yourserver.com')
        ftp.login(user='yourftpuser', passwd='yourftppassword')
        with open(file_path, 'rb') as f:
            ftp.storbinary(f'STOR {submission["id"]}.py', f)
        ftp.quit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"FTP 전송 실패: {e}")

    update_query = ("UPDATE submissions SET status = %s, updated_at = %s WHERE id = %s")
    cursor.execute(update_query, ('PROCESSING', datetime.utcnow(), submission['id']))
    cnx.commit()

    cursor.close()
    cnx.close()

    logger.info(f"Submission processed: {submission['id']}")

    return {"detail": "성공적으로 제출되었습니다."}

@app.patch("/submission")
async def update_status(update: UpdateStatus):
    cnx = get_db()
    if not cnx:
        raise HTTPException(status_code=500, detail="데이터베이스에 연결하지 못했습니다.")
    
    cursor = cnx.cursor()
    update_query = ("UPDATE submissions SET status = %s, updated_at = %s WHERE id = %s")
    cursor.execute(update_query, (update.status, datetime.utcnow(), update.id))
    cnx.commit()

    cursor.close()
    cnx.close()

    logger.info(f"Submission status updated: {update.id}")

    return {"detail": "제출 상태가 갱신되었습니다."}

@app.get("/submission")
async def get_submission_result(username: str, password: str, id: int):
    cnx = get_db()
    if not cnx:
        raise HTTPException(status_code=500, detail="데이터베이스에 연결하지 못했습니다.")
    
    cursor = cnx.cursor(dictionary=True)
    query = ("SELECT id, username, password, status FROM submissions WHERE username = %s AND id = %s")
    cursor.execute(query, (username, id))
    submission = cursor.fetchone()

    if not submission:
        cursor.close()
        cnx.close()
        raise HTTPException(status_code=404, detail="제출된 코드를 찾지 못했습니다.")

    if submission['password'] != password:
        cursor.close()
        cnx.close()
        raise HTTPException(status_code=401, detail="Unauthorized")

    cursor.close()
    cnx.close()

    logger.info(f"Submission result fetched: {submission['id']}")

    return {"status": submission['status']}
