# Zoyina Pesa v2 — Maelekezo ya Ufungaji

## Hatua za Kwanza (Mara ya Kwanza)

```bash
# 1. Sakinisha vitegemezi
pip install -r requirements.txt

# 2. Endesha migration ya database (MUHIMU!)
python migrate.py

# 3. Anza server
python app.py
```

## Maelekezo ya Kusasisha kutoka Toleo la Zamani

Kama una database ya zamani:
```bash
python migrate.py   # ongeza tables mpya bila kupoteza data
python app.py       # anza server
```

## Mfumo wa Matangazo Mpya (v2)

### Jinsi Inavyofanya Kazi:
1. Admin anaunda **Kikundi** (mfano: "YouTube Ads - Feb 2025")
   - Chagua platform: YouTube / TikTok / Facebook / Instagram / Twitter / Nyingine
   - Weka muda wa kutazama (sekunde) — inabadilika kwa platform
   - Weka malipo kwa kila tangazo
   
2. Admin anaongeza **Matangazo** ndani ya kikundi (URL au faili)

3. Mtumiaji anaona **vitufe vya platform** (YouTube, TikTok, n.k.)

4. Bonyeza platform → orodha ya matangazo yenye lock/unlock sequential

5. Kila tangazo linafunguka moja baada ya nyingine

6. Baada ya kukamilisha kikundi chote → haionekani tena leo

7. Siku ijayo → matangazo yanarudi

### Muda wa Kutazama kwa Platform:
| Platform  | Sekunde |
|-----------|---------|
| YouTube   | 60s     |
| TikTok    | 60s     |
| Facebook  | 90s     |
| Instagram | 60s     |
| Twitter   | 45s     |
| Nyingine  | 30s     |

## Admin Panel
- URL: /admin
- Username: admin (au env: ADMIN_USERNAME)
- Password: admin123 (au env: ADMIN_PASSWORD)

### Usimamizi wa Rufaa:
- Bonyeza **+Rufaa** ili kuongeza ghost referrals (na/bila bonus)
- Bonyeza **-Rufaa** ili kufuta ghost referrals (na/bila kupunguza bonus)
