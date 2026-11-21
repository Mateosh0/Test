import os, sqlite3, secrets, string, csv, io
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, request, session, redirect, url_for, render_template_string, flash, Response
from werkzeug.security import generate_password_hash, check_password_hash

app=Flask(__name__)
app.secret_key=os.getenv('SECRET_KEY',secrets.token_hex(32))
DB=os.getenv('DB_PATH',os.path.join(os.path.dirname(__file__),'mctime.sqlite3'))
CREATE_CODE=os.getenv('ADMIN_CREATE_CODE','1786')

def db():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c

def init():
 with db() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS admins(id INTEGER PRIMARY KEY,restaurant TEXT NOT NULL,fullname TEXT NOT NULL,username TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS employees(id INTEGER PRIMARY KEY,restaurant TEXT NOT NULL,punch TEXT NOT NULL,fullname TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,UNIQUE(restaurant,punch));
CREATE TABLE IF NOT EXISTS shifts(id INTEGER PRIMARY KEY,employee_id INTEGER NOT NULL REFERENCES employees(id),started TEXT NOT NULL,ended TEXT);
CREATE TABLE IF NOT EXISTS breaks(id INTEGER PRIMARY KEY,shift_id INTEGER NOT NULL REFERENCES shifts(id),started TEXT NOT NULL,ended TEXT);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,employee_id INTEGER NOT NULL REFERENCES employees(id),shift_id INTEGER,kind TEXT NOT NULL,at TEXT NOT NULL,restaurant TEXT NOT NULL);''')
init()
def now():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def stamp(s):return datetime.fromisoformat(s).astimezone().strftime('%d.%m.%Y %H:%M:%S') if s else '—'
app.jinja_env.filters['stamp']=stamp

def auth(fn):
 @wraps(fn)
 def wrapper(*a,**kw):
  if not session.get('admin_id'):return redirect(url_for('login'))
  return fn(*a,**kw)
 return wrapper

BASE='''<!doctype html><html lang="uk"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>McTime</title><style>
:root{color-scheme:dark;font-family:system-ui,-apple-system,Segoe UI,sans-serif}*{box-sizing:border-box}body{margin:0;background:#101114;color:#f5f5f5}main{max-width:940px;margin:35px auto;padding:16px}.brand{font-size:28px;font-weight:800;color:#ffca28}.sub{color:#aaa;font-size:13px}.card{background:#1b1d22;border:1px solid #35363b;border-radius:18px;padding:24px;margin:18px 0}.narrow{max-width:480px;margin:45px auto}h1{font-size:26px;margin:12px 0}h2{font-size:19px}p{line-height:1.5}a{color:#ffcf43}label{display:block;margin:15px 0 6px;color:#ddd}input,select{display:block;width:100%;background:#101114;border:1px solid #51545c;border-radius:10px;color:white;padding:13px;font:inherit}button,.btn{border:0;display:inline-block;text-align:center;text-decoration:none;cursor:pointer;border-radius:11px;padding:13px 17px;font:inherit;font-weight:700;color:#111;background:#ffca28;margin:5px 4px 5px 0}.btn:hover,button:hover{filter:brightness(1.08)}button:disabled{opacity:.32;cursor:not-allowed}.green{background:#35ce78}.red{background:#ff6868}.yellow{background:#ffcb32}.blue{background:#65a8ff}.muted{background:#41444c;color:#fff}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.grid>*{width:100%;margin:0}.msg{background:#38332a;border:1px solid #8c7228;padding:12px;border-radius:9px;margin:10px 0}.nav{display:flex;justify-content:space-between;align-items:center;gap:10px}.tablewrap{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px}td,th{border-bottom:1px solid #3a3b41;text-align:left;padding:11px;white-space:nowrap}th{color:#ffca28}.pill{background:#30363b;border-radius:20px;padding:6px 12px;display:inline-block}.hint{color:#aaa;font-size:13px}.inline{display:inline}.inline button{padding:8px}.full{width:100%}@media(max-width:520px){main{margin:12px auto}.card{padding:18px}.grid{grid-template-columns:1fr}}
</style></head><body><main><div class="nav"><a class="brand" href="/" style="text-decoration:none">◷ McTime</a><span class="sub">Employee Time Tracking</span></div>{% with msgs=get_flashed_messages() %}{% for msg in msgs %}<div class="msg">{{msg}}</div>{% endfor %}{% endwith %}{{content|safe}}<p class="hint">Незалежна система обліку часу. Не є офіційним продуктом McDonald's.</p></main></body></html>'''
def page(t,**ctx):
 content=render_template_string(t,**ctx)
 return render_template_string(BASE,content=content)

@app.route('/')
def home():return page('''<div class="card narrow"><h1>Вітаємо!</h1><p class="sub">Оберіть спосіб входу</p><a class="btn yellow full" href="{{url_for('worker')}}">👤 Увійти як працівник</a><a class="btn muted full" href="{{url_for('login')}}">🛡 Адміністративний помічник</a></div>''')

@app.route('/worker',methods=['GET','POST'])
def worker():
 employee=None; status=None
 if request.method=='POST':
  restaurant=request.form.get('restaurant','').strip(); punch=request.form.get('punch','').strip()
  with db() as c:
   employee=c.execute('SELECT * FROM employees WHERE restaurant=? AND punch=? AND active=1',(restaurant,punch)).fetchone()
   if employee:
    shift=c.execute('SELECT * FROM shifts WHERE employee_id=? AND ended IS NULL ORDER BY id DESC LIMIT 1',(employee['id'],)).fetchone()
    br=c.execute('SELECT * FROM breaks WHERE shift_id=? AND ended IS NULL ORDER BY id DESC LIMIT 1',(shift['id'],)).fetchone() if shift else None
    status='break' if br else ('working' if shift else 'idle')
   else:flash('Панч-номер не знайдено для цього ресторану або працівник неактивний.')
 return page('''<div class="card narrow"><h1>Термінал працівника</h1>{% if not employee %}<form method="post"><label>Номер ресторану</label><input name="restaurant" required autocomplete="off" value="{{request.form.get('restaurant','')}}"><label>Панч-номер</label><input name="punch" required autocomplete="off" inputmode="numeric"><button class="yellow full">Продовжити</button></form>{% else %}<h2>{{employee.fullname}}</h2><p class="pill">{% if status=='idle' %}Поза зміною{% elif status=='working' %}На зміні{% else %}На перерві{% endif %}</p><form method="post" action="{{url_for('worker_action')}}"><input type="hidden" name="restaurant" value="{{employee.restaurant}}"><input type="hidden" name="punch" value="{{employee.punch}}">{% if status=='break' %}<button name="action" value="break_end" class="yellow full">Завершити перерву</button>{% else %}<div class="grid"><button name="action" value="start" class="green" {% if status!='idle' %}disabled{% endif %}>Розпочати зміну</button><button name="action" value="end" class="red" {% if status!='working' %}disabled{% endif %}>Закінчити зміну</button><button name="action" value="break_start" class="yellow" {% if status!='working' %}disabled{% endif %}>Розпочати перерву</button><a class="btn blue" href="/">Повернутись назад</a></div>{% endif %}</form>{% endif %}<a href="/">← Головна</a></div>''',employee=employee,status=status)

@app.post('/worker/action')
def worker_action():
 restaurant=request.form.get('restaurant','').strip();punch=request.form.get('punch','').strip();action=request.form.get('action')
 with db() as c:
  c.execute('BEGIN IMMEDIATE')
  emp=c.execute('SELECT * FROM employees WHERE restaurant=? AND punch=? AND active=1',(restaurant,punch)).fetchone()
  if not emp:flash('Працівника не знайдено.');return redirect('/worker')
  shift=c.execute('SELECT * FROM shifts WHERE employee_id=? AND ended IS NULL ORDER BY id DESC LIMIT 1',(emp['id'],)).fetchone()
  br=c.execute('SELECT * FROM breaks WHERE shift_id=? AND ended IS NULL ORDER BY id DESC LIMIT 1',(shift['id'],)).fetchone() if shift else None
  t=now();sid=shift['id'] if shift else None;kind=None
  if action=='start' and not shift:
   sid=c.execute('INSERT INTO shifts(employee_id,started) VALUES(?,?)',(emp['id'],t)).lastrowid;kind='shift_start'
  elif action=='end' and shift and not br:
   c.execute('UPDATE shifts SET ended=? WHERE id=?',(t,sid));kind='shift_end'
  elif action=='break_start' and shift and not br:
   c.execute('INSERT INTO breaks(shift_id,started) VALUES(?,?)',(sid,t));kind='break_start'
  elif action=='break_end' and br:
   c.execute('UPDATE breaks SET ended=? WHERE id=?',(t,br['id']));kind='break_end'
  if kind:c.execute('INSERT INTO events(employee_id,shift_id,kind,at,restaurant) VALUES(?,?,?,?,?)',(emp['id'],sid,kind,t,restaurant))
  else:flash('Ця дія зараз недоступна.');return redirect('/worker')
 flash('Операцію збережено. Дякуємо!')
 return redirect('/')

@app.route('/admin/register',methods=['GET','POST'])
def register():
 if request.method=='POST':
  restaurant=request.form.get('restaurant','').strip();fullname=request.form.get('fullname','').strip();code=request.form.get('code','')
  if code!=CREATE_CODE or not restaurant or not fullname:flash('Перевірте дані та код реєстрації.')
  else:
   alphabet=string.ascii_letters+string.digits
   password=''.join(secrets.choice(alphabet) for _ in range(16))
   with db() as c:
    while True:
     username='mc'+''.join(secrets.choice(string.digits) for _ in range(8))
     if not c.execute('SELECT 1 FROM admins WHERE username=?',(username,)).fetchone():break
    c.execute('INSERT INTO admins(restaurant,fullname,username,password_hash,created_at) VALUES(?,?,?,?,?)',(restaurant,fullname,username,generate_password_hash(password),now()))
   return page('''<div class="card narrow"><h1>Акаунт створено</h1><p>Збережіть ці дані зараз. Пароль більше не відображатиметься.</p><label>Логін</label><input readonly value="{{username}}"><label>Пароль</label><input readonly value="{{password}}"><a class="btn yellow full" href="/admin/login">Перейти до входу</a></div>''',username=username,password=password)
 return page('''<div class="card narrow"><h1>Реєстрація помічника</h1><form method="post"><label>Номер ресторану</label><input name="restaurant" required><label>Ім'я та прізвище</label><input name="fullname" required><label>Код створення акаунта</label><input name="code" type="password" required><button class="yellow full">Створити акаунт</button></form><a href="/admin/login">Уже є акаунт?</a></div>''')

@app.route('/admin/login',methods=['GET','POST'])
def login():
 if request.method=='POST':
  with db() as c:admin=c.execute('SELECT * FROM admins WHERE username=?',(request.form.get('username','').strip(),)).fetchone()
  if admin and check_password_hash(admin['password_hash'],request.form.get('password','')):
   session.clear();session['admin_id']=admin['id'];session['restaurant']=admin['restaurant'];session['fullname']=admin['fullname'];return redirect('/admin')
  flash('Неправильний логін або пароль.')
 return page('''<div class="card narrow"><h1>Адміністративний помічник</h1><form method="post"><label>Логін</label><input name="username" required><label>Пароль</label><input name="password" type="password" required><button class="yellow full">Увійти</button></form><a href="/admin/register">Створити акаунт</a></div>''')

@app.post('/admin/logout')
def logout():session.clear();return redirect('/')

@app.get('/admin')
@auth
def dashboard():
 with db() as c:
  employees=c.execute('SELECT e.*, (SELECT COUNT(*) FROM shifts s WHERE s.employee_id=e.id AND s.ended IS NULL) as on_shift,(SELECT COUNT(*) FROM breaks b JOIN shifts s ON s.id=b.shift_id WHERE s.employee_id=e.id AND b.ended IS NULL) as on_break FROM employees e WHERE e.restaurant=? ORDER BY e.fullname',(session['restaurant'],)).fetchall()
  events=c.execute('SELECT v.*,e.fullname,e.punch FROM events v JOIN employees e ON e.id=v.employee_id WHERE v.restaurant=? ORDER BY v.id DESC LIMIT 100',(session['restaurant'],)).fetchall()
  shifts=c.execute('SELECT s.*,e.fullname,e.punch FROM shifts s JOIN employees e ON e.id=s.employee_id WHERE e.restaurant=? ORDER BY s.id DESC LIMIT 50',(session['restaurant'],)).fetchall()
 return page('''<div class="nav"><div><h1>Панель адміністратора</h1><p class="sub">{{session.fullname}} · Ресторан №{{session.restaurant}}</p></div><form action="/admin/logout" method="post"><button class="muted">Вийти</button></form></div><div class="card"><h2>Зареєструвати працівника</h2><form method="post" action="/admin/employees"><label>Ім'я та прізвище</label><input name="fullname" required><label>Панч-номер</label><input name="punch" required><button class="yellow">Додати працівника</button></form></div><div class="card"><h2>Працівники ({{employees|length}})</h2><div class="tablewrap"><table><tr><th>Ім'я</th><th>Панч</th><th>Статус</th><th>Дія</th></tr>{% for e in employees %}<tr><td>{{e.fullname}}</td><td>{{e.punch}}</td><td>{% if not e.active %}Неактивний{% elif e.on_break %}Перерва{% elif e.on_shift %}На зміні{% else %}Поза зміною{% endif %}</td><td><form class="inline" method="post" action="/admin/employees/{{e.id}}/toggle"><button class="muted">{{'Деактивувати' if e.active else 'Активувати'}}</button></form></td></tr>{% endfor %}</table></div></div><div class="card"><div class="nav"><h2>Журнал подій</h2><a class="btn blue" href="/admin/export">Експорт CSV</a></div><div class="tablewrap"><table><tr><th>Час</th><th>Працівник</th><th>Панч</th><th>Подія</th></tr>{% for e in events %}<tr><td>{{e.at|stamp}}</td><td>{{e.fullname}}</td><td>{{e.punch}}</td><td>{{{'shift_start':'Початок зміни','shift_end':'Кінець зміни','break_start':'Початок перерви','break_end':'Кінець перерви'}[e.kind]}}</td></tr>{% endfor %}</table></div></div><div class="card"><h2>Історія змін</h2><div class="tablewrap"><table><tr><th>Працівник</th><th>Початок</th><th>Кінець</th><th>Тривалість зміни</th></tr>{% for s in shifts %}<tr><td>{{s.fullname}} ({{s.punch}})</td><td>{{s.started|stamp}}</td><td>{{s.ended|stamp}}</td><td>{% if s.ended %}{{((parse_date(s.ended)-parse_date(s.started)).total_seconds()/3600)|round(2)}} год{% else %}Триває{% endif %}</td></tr>{% endfor %}</table></div><p class="hint">Тривалість зміни в цій таблиці включає перерви. Журнал подій зберігає їх окремо.</p></div>''',employees=employees,events=events,shifts=shifts,parse_date=datetime.fromisoformat)

@app.post('/admin/employees')
@auth
def add_employee():
 fullname=request.form.get('fullname','').strip();punch=request.form.get('punch','').strip()
 if not fullname or not punch:flash('Заповніть усі поля.')
 else:
  try:
   with db() as c:c.execute('INSERT INTO employees(restaurant,punch,fullname,created_at) VALUES(?,?,?,?)',(session['restaurant'],punch,fullname,now()))
   flash('Працівника додано.')
  except sqlite3.IntegrityError:flash('Такий панч-номер уже існує в цьому ресторані.')
 return redirect('/admin')

@app.post('/admin/employees/<int:eid>/toggle')
@auth
def toggle(eid):
 with db() as c:
  e=c.execute('SELECT * FROM employees WHERE id=? AND restaurant=?',(eid,session['restaurant'])).fetchone()
  if e:
   active=not bool(e['active'])
   if not active and c.execute('SELECT 1 FROM shifts WHERE employee_id=? AND ended IS NULL',(eid,)).fetchone():flash('Не можна деактивувати працівника під час зміни.')
   else:c.execute('UPDATE employees SET active=? WHERE id=?',(int(active),eid));flash('Статус працівника змінено.')
 return redirect('/admin')

@app.get('/admin/export')
@auth
def export():
 with db() as c:rows=c.execute('SELECT v.at,v.kind,e.fullname,e.punch,v.restaurant FROM events v JOIN employees e ON e.id=v.employee_id WHERE v.restaurant=? ORDER BY v.id',(session['restaurant'],)).fetchall()
 output=io.StringIO();writer=csv.writer(output);writer.writerow(['UTC time','event','employee','punch','restaurant']);writer.writerows([list(r) for r in rows]);return Response('\ufeff'+output.getvalue(),mimetype='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename=mctime_events.csv'})

if __name__=='__main__':app.run(host='127.0.0.1',port=int(os.getenv('PORT','5000')),debug=False)
