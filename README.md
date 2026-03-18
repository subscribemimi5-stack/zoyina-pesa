# 💰 Zoyina Pesa — Mfumo wa Mapato ya Rufaa

Mfumo wa wavuti wa Python/Flask kwa ajili ya kusimamia programu ya rufaa ya fedha.

## 📁 Muundo wa Mradi

```
zoyina_pesa/
├── app.py              ← Msingi wa programu (routes na logic)
├── models.py           ← Mifano ya database (User, Transaction)
├── requirements.txt    ← Vifaa vinavyohitajika
└── templates/
    ├── base.html       ← Kiolezo cha msingi
    ├── login.html      ← Ukurasa wa kuingia
    ├── register.html   ← Ukurasa wa kusajili
    └── dashboard.html  ← Dashibodi ya mtumiaji
```

## 🚀 Jinsi ya Kuanza

### 1. Sakinisha vifaa
```bash
pip install -r requirements.txt
```

### 2. Endesha programu
```bash
python app.py
```

### 3. Fungua kivinjari
```
http://localhost:5000
```

## ✨ Vipengele

| Kipengele | Maelezo |
|-----------|---------|
| 📝 Usajili | Akaunti moja kwa IP moja (kinga dhidi ya ulaghai) |
| 🔒 Usalama | Nywila zimefichwa (Werkzeug hashing) |
| 💰 Bonus ya Rufaa | Tsh 500 kwa kila mtu unayemleta |
| 💸 Kutoa Pesa | Kiwango cha chini Tsh 2,000 |
| 📊 Miamala | Historia kamili ya mapato na matumizi |
| 🔗 Link ya Rufaa | Unaweza kushiriki link moja kwa moja |
| 📱 Mobile-Friendly | Inafanya kazi vizuri kwenye simu |

## ⚙️ Mipangilio (app.py)

```python
REFERRAL_BONUS = 500.0    # Bonus kwa kila rufaa iliyofanikiwa
MIN_WITHDRAWAL = 2000.0   # Kiwango cha chini cha kutoa
```

## 🔐 Usalama wa Uzalishaji

Kabla ya kupeleka kwenye seva halisi:

1. **Badilisha SECRET_KEY** - Weka `SECRET_KEY` kwenye variable ya mazingira:
   ```bash
   export SECRET_KEY="nywila_yako_ngumu_sana_hapa"
   ```

2. **Badilisha Database** - Tumia PostgreSQL au MySQL badala ya SQLite

3. **Zima debug mode** - Badilisha `app.run(debug=True)` kuwa `app.run(debug=False)`

4. **Ongeza HTTPS** - Tumia Nginx au Gunicorn mbele ya Flask

## 📞 API Endpoints

| Method | URL | Maelezo |
|--------|-----|---------|
| GET | `/` | Kuhamia login |
| GET | `/login_page` | Ukurasa wa kuingia |
| GET | `/register_page` | Ukurasa wa kusajili |
| GET | `/dashboard` | Dashibodi (lazima uwe umeingia) |
| POST | `/login` | API ya kuingia |
| POST | `/register` | API ya kusajili |
| POST | `/withdraw` | API ya kutoa pesa |
| GET | `/logout` | Kutoka |
| GET | `/api/stats` | Data ya akaunti (JSON) |
"# zoyina-pesa" 
