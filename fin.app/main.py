from fastapi import FastAPI, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Optional
import pymysql
import aiomysql
import os
from datetime import datetime
import ftplib
import uvicorn

app = FastAPI()

# MySQL connection details
DB_HOST = "localhost"
DB_PORT = 3306
DB_USER = "your_mysql_user"
DB_PASSWORD = "your_mysql_password"
DB_NAME = "code_management"

# FTP server details
FTP_HOST = "E_IP_ADDRESS"
FTP_USER = "yeonjun"
FTP_PASSWORD = "1234567890"

class Submission(BaseModel):
    username: str
    password: str
    submission_dir: str

class UpdateStatus(BaseModel):
    id: int
    status: str

# Function to get MySQL connection
async def get_db():
    conn = await aiomysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, db=DB_NAME)
    return conn

# 기능 1: 코드 제출
@app.post("/submission")
async def submit_code(submission: Submission):
    async with await get_db() as conn:
        async with conn.cursor() as cursor:
            sql = "INSERT INTO submissions (username, password, submission_dir, status) VALUES (%s, %s, %s, 'SUBMITTED')"
            await cursor.execute(sql, (submission.username, submission.password, submission.submission_dir))
            await conn.commit()
            submission_id = cursor.lastrowid
            return {"id": submission_id}

# 기능 2: E로 코드 전달
@app.get("/new")
async def get_new_code():
    async with await get_db() as conn:
        async with conn.cursor() as cursor:
            sql = "SELECT * FROM submissions WHERE status='SUBMITTED' ORDER BY created_at ASC LIMIT 1"
            await cursor.execute(sql)
            result = await cursor.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="No submissions found")
            
            submission_id, username, password, submission_dir, status, created_at, updated_at = result

            # FTP 전송
            try:
                ftp = ftplib.FTP(FTP_HOST)
                ftp.login(FTP_USER, FTP_PASSWORD)
                filename = os.path.basename(submission_dir)
                with open(submission_dir, 'rb') as file:
                    ftp.storbinary(f"STOR {filename}", file)
                ftp.quit()
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"FTP transfer failed: {e}")

            # 상태 업데이트
            sql = "UPDATE submissions SET status='PROCESSING', updated_at=%s WHERE id=%s"
            await cursor.execute(sql, (datetime.now(), submission_id))
            await conn.commit()

            return {"status": "success"}

# 기능 3: 실행 결과 업데이트
@app.patch("/submission")
async def update_submission_status(update: UpdateStatus):
    async with await get_db() as conn:
        async with conn.cursor() as cursor:
            sql = "UPDATE submissions SET status=%s, updated_at=%s WHERE id=%s"
            await cursor.execute(sql, (update.status, datetime.now(), update.id))
            await conn.commit()
            return {"status": "success"}

# 기능 4: 결과 확인
@app.get("/submission")
async def get_submission_status(id: int, username: str, password: str):
    async with await get_db() as conn:
        async with conn.cursor() as cursor:
            sql = "SELECT * FROM submissions WHERE id=%s AND username=%s"
            await cursor.execute(sql, (id, username))
            result = await cursor.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="Submission not found")

            db_id, db_username, db_password, submission_dir, status, created_at, updated_at = result

            if db_password != password:
                raise HTTPException(status_code=401, detail="Unauthorized")

            return {"id": db_id, "username": db_username, "status": status, "created_at": created_at, "updated_at": updated_at}

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python manage_server.py <C_IP_ADDRESS> <E_IP_ADDRESS>")
        sys.exit(1)
    
    C_IP_ADDRESS = sys.argv[1]
    E_IP_ADDRESS = sys.argv[2]

    # Adjust FTP_HOST based on the provided E_IP_ADDRESS
    FTP_HOST = E_IP_ADDRESS

    uvicorn.run(app, host="0.0.0.0", port=8000)