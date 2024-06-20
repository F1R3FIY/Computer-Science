from fastapi import FastAPI, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import os
import ftplib
import mysql.connector
from mysql.connector import errorcode

app = FastAPI()

def get_db():
    try:
        cnx = mysql.connector.connect(user='youruser', password='yourpassword',
                                      host='yourhost',
                                      database='yourdatabase')
        return cnx
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("아이디 혹은 비밀번호가 틀렸습니다.")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("존재하지 않는 계정입니다.")
        else:
            print(err)
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
    add_submission = ("제출란에 입력 "
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

    return {"예약 번호": submission_id}

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

    return {"detail": "제출 상태가 갱신되었습니다."}

@app.get("/submission")
async def get_submission_result(result: ExecutionResult):
    cnx = get_db()
    if not cnx:
        raise HTTPException(status_code=500, detail="데이터베이스에 연결하지 못했습니다.")
    
    cursor = cnx.cursor(dictionary=True)
    query = ("SELECT id, username, password, status FROM submissions WHERE username = %s AND id = %s")
    cursor.execute(query, (result.username, result.id))
    submission = cursor.fetchone()

    if not submission:
        cursor.close()
        cnx.close()
        raise HTTPException(status_code=404, detail="제출된 코드를 찾지 못했습니다.")

    if submission['password'] != result.password:
        cursor.close()
        cnx.close()
        raise HTTPException(status_code=401, detail="Unauthorized")

    cursor.close()
    cnx.close()

    return {"status": submission['status']}
