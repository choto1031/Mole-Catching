import os, sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
BASE=Path(__file__).resolve().parent
DB=Path(os.getenv("DUDOGI_DB_PATH", str(BASE/"scores.db")))
MAX_SCORE=10000000
app=FastAPI(title="커스텀 두더지 잡기")
def init():
 DB.parent.mkdir(parents=True,exist_ok=True)
 with closing(sqlite3.connect(DB)) as c:
  c.execute("CREATE TABLE IF NOT EXISTS scores(id INTEGER PRIMARY KEY AUTOINCREMENT,nickname TEXT NOT NULL,score INTEGER NOT NULL,created_at TEXT NOT NULL)")
  duplicates=c.execute("SELECT nickname,COUNT(*) FROM scores GROUP BY nickname HAVING COUNT(*)>1").fetchall()
  for nickname,_ in duplicates:
   keep=c.execute("SELECT id FROM scores WHERE nickname=? ORDER BY score DESC,id ASC LIMIT 1",(nickname,)).fetchone()
   c.execute("DELETE FROM scores WHERE nickname=? AND id<>?",(nickname,keep[0]))
  c.commit()
init()
class Score(BaseModel):
 nickname:str
 score:int=Field(...,ge=0,le=MAX_SCORE)
 @field_validator("nickname")
 @classmethod
 def nick(cls,v):
  v=v.strip()
  if not 1<=len(v)<=12: raise ValueError("닉네임은 1~12자여야 합니다.")
  return v
 @field_validator("score")
 @classmethod
 def points(cls,v):
  if isinstance(v,bool) or v<0 or v>MAX_SCORE: raise ValueError("점수는 0 이상 10,000,000 이하의 정수여야 합니다.")
  return v
@app.get("/health")
def health(): return {"status":"ok"}
@app.get("/api/rankings")
def rankings():
 with closing(sqlite3.connect(DB)) as c: rows=c.execute("SELECT id,nickname,score,created_at FROM scores ORDER BY score DESC,id ASC LIMIT 10").fetchall()
 return [{"rank":i+1,"id":r[0],"nickname":r[1],"score":r[2],"created_at":r[3]} for i,r in enumerate(rows)]
@app.post("/api/scores",status_code=201)
def add_score(p:Score):
 now=datetime.now(timezone.utc).isoformat()
 with closing(sqlite3.connect(DB)) as c:
  existing=c.execute("SELECT id,score FROM scores WHERE nickname=?",(p.nickname,)).fetchone()
  if existing:
   if p.score>existing[1]:
    c.execute("UPDATE scores SET score=?,created_at=? WHERE id=?",(p.score,now,existing[0]))
    c.commit()
    return {"id":existing[0],"updated":True,"message":"최고 기록이 갱신되었습니다."}
   return {"id":existing[0],"updated":False,"message":"기존 최고 기록이 더 높아 유지되었습니다."}
  cur=c.execute("INSERT INTO scores(nickname,score,created_at) VALUES(?,?,?)",(p.nickname,p.score,now));c.commit()
 return {"id":cur.lastrowid,"updated":True,"message":"점수가 등록되었습니다."}
@app.get("/")
def index(): return FileResponse(BASE/"static/index.html")
from fastapi.staticfiles import StaticFiles
app.mount("/static",StaticFiles(directory=BASE/"static"),name="static")
