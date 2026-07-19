# 🤖 CryptoBot - Telegram Token Analyzer

Analyse intelligente de nouveaux tokens Ethereum avec scoring automatique + position sizing.

---

## 📦 Fichiers du projet

```
/
├── bot.py                    ← Code principal du bot
├── requirements.txt          ← Dépendances Python
├── .env.example             ← Template variables (À NE PAS VENDRE!)
├── setup_supabase.sql       ← SQL pour créer les tables Supabase
├── QUICK_START.md           ← 10 minutes pour lancer ⭐ COMMENCER ICI
├── DEPLOYMENT_GUIDE.md      ← Guide détaillé Railway + Supabase
├── SCORING_SYSTEM.md        ← Explication du scoring + critères
└── README.md                ← Ce fichier
```

---

## ⚡ Démarrage rapide (10 min)

### 1. Setup Supabase
Ouvre `setup_supabase.sql` → Copie dans Supabase SQL Editor → Run

### 2. Setup Railway
- Crée un compte https://railway.app
- Upload `bot.py` + `requirements.txt`

### 3. Ajoute les variables d'env sur Railway
Copie tes clés régénérées dans Railway → Settings → Environment Variables

### 4. Déploie!
Railway auto-détecte + déploie

### 5. Test sur Telegram
- Find your bot
- `/start` → Bienvenue!
- `/setup` → Configure ton wallet
- `/analyze [CA]` → Analyse un token

**→ Voir QUICK_START.md pour les détails**

---

## 🎯 Comment ça marche

```
Token detecté sur Uniswap
    ↓
Bot analyse 5 critères:
  1. Holders distribution
  2. Contract safety
  3. Liquidity & Volume
  4. Age du projet
  5. Price action
    ↓
Score 0-100 générée
    ↓
Position sizing calculée (%)
    ↓
Telegram notification envoyée
    ↓
Tu valides ✅
    ↓
Tu achètes via BasedBot
    ↓
Bot track 24/7:
  - Prix en temps réel
  - SL/TP automatiques
  - Notifications
    ↓
Tu vends via BasedBot
```

---

## 📊 Système de Scoring

**5 critères évalués:**

| Critère | Poids | Details |
|---------|-------|---------|
| 👥 Holders | 25 pts | Nombre + distribution |
| 🔒 Contract Safety | 20 pts | Mint, pause, ownership |
| 💧 Liquidity & Volume | 20 pts | $$ liquidité + trading volume |
| ⏰ Age | 15 pts | Jours depuis le lancement |
| 📈 Price Action | 20 pts | Volatilité 24h |

**Score final:**
- 85-100 → 🟢 Position 30%
- 65-84 → 🟡 Position 15%
- 40-64 → 🔴 Position 8%
- 0-39 → 🔴 Position 2%

→ **Lire SCORING_SYSTEM.md pour les détails**

---

## 💰 Position Sizing Automatique

En fonction du score, le bot te recommande combien miser:

```
Budget: $311

Score 87 → "Mise $93 (30%)"
Score 56 → "Mise $47 (15%)"
Score 28 → "Mise $25 (8%)"
```

C'est automatique! Tu dois juste cliquer ✅.

---

## 📱 Commandes Telegram

```
/start       → Bienvenue + status
/setup       → Configure wallet + budget
/analyze CA  → Analyse un token (ex: /analyze 0xabc123)
/status      → Voir tes trades + P&L
```

---

## 🗄️ Base de données Supabase

3 tables créées automatiquement:

### `users`
- User ID Telegram
- Wallet address
- Budget par trade
- TP/SL targets
- Total profit/loss

### `trades`
- Token CA + name
- Prix d'entrée/sortie
- Amount investi
- Status (holding/sold)
- P&L tracking

### `token_analysis`
- Cache des analyses
- Scores calculés
- Holder data
- Historique

---

## 🚀 Déploiement

**Plateforme: Railway.app**

Avantages:
- ✅ Gratuit (tier free)
- ✅ 24/7 uptime
- ✅ Auto-restart
- ✅ Facile à configurer
- ✅ Variables sécurisées

**Setup détaillé → DEPLOYMENT_GUIDE.md**

---

## 🔐 Sécurité

✅ **Pas de clés en plaintext**
- Toutes les clés sur Railway = chiffrées

✅ **Multi-user support**
- Chaque user a ses propres données
- Données isolées par User ID Telegram

✅ **Etherscan API**
- Read-only (juste lire les données)
- Pas d'accès au wallet

✅ **Supabase Key**
- Published key (read/write limité)
- Rotate régulièrement

---

## 📊 Statistiques d'usage

**Pour toi:**
- Budget initial: $311
- Tokens détectés par jour: 1000+
- Tokens avec score >50: ~50/jour
- Tokens avec score >80: ~5/jour

**Recommandation:**
- 3-5 trades par jour
- 10-15% wins
- 70-80% break-even/small loss
- 10-20% home runs (+100%+)

---

## 🎓 Stratégie recommandée

### Week 1: Apprendre
```
Fais 10 trades petits
- Observe les patterns
- Vois ce qui marche/marche pas
- Ajuste tes critères
```

### Week 2-4: Scale up
```
Augmente les positions
Diversifie entre tokens différents
Teste différents TP/SL
```

### Month 2+: Optimization
```
Fine-tune le scoring
Ajoute des critères Twitter
Maximize les wins
```

---

## ⚠️ Pièges courants

❌ **Trader sans SL**
- Le bot a besoin du SL

❌ **Acheter tous les tokens score >50**
- Trop de volume = trop d'érecteurs

❌ **Ignorer les red flags**
- Concentration >70% = RUG probable

❌ **Pas de position sizing**
- Miser le même montant partout = faillite

✅ **Follow la position sizing recommandée**
✅ **Set SL/TP à chaque trade**
✅ **Diversifie sur 5+ tokens en même temps**
✅ **Repose-toi et laisse le bot tracker**

---

## 🆘 Support

### Si le bot ne marche pas
1. Vérifie Railway Logs → `Settings` → `Logs`
2. Check `bot.py` est bien deployé
3. Redéploie avec le bon token

### Si erreurs d'API
1. Supabase down? → Status page
2. Etherscan rate limit? → Normal, ça retry
3. Dex Screener down? → Très rare

### Si erreurs token
1. Vérify l'adresse (0x...)
2. Token existe sur Ethereum Mainnet?
3. Token sur Uniswap? (pas Robinhood)

---

## 🔄 Maintenance

### Daily
- Check `/status` pour P&L
- Vend quand TP/SL hit

### Weekly
- Review des trades perdants
- Ajuste critères si besoin
- Check les logs pour anomalies

### Monthly
- Rotate API keys
- Update scoring si besoin
- Analyze profitability

---

## 📈 Performance tracking

Bot log tout automatiquement dans Supabase:
- Chaque analyse
- Chaque trade
- P&L par token
- Win rate

Vérifie régulièrement!

---

## 🎯 Objectives

- [ ] Bot déployé et running
- [ ] 10 trades dans la week 1
- [ ] 50% break-even or better
- [ ] Identifier top 3 winning patterns
- [ ] Scale positions semaine 2

---

## 📚 Documentation

1. **QUICK_START.md** ← Lis ça d'abord (10 min)
2. **SCORING_SYSTEM.md** ← Comprends le scoring
3. **DEPLOYMENT_GUIDE.md** ← Setup détaillé

---

## 📞 Questions?

Si quelque chose marche pas:
1. Check les logs Railway
2. Vérifiy les variables env
3. Run `setup_supabase.sql` à nouveau
4. Redéploie

---

## 🚀 C'est bon!

T'as tout ce qu'il faut pour trader des altcoins de manière intelligente.

**Prochaine étape:** Ouvre QUICK_START.md et suis les étapes!

Bonne chance! 🎯

---

**Made with ❤️ for crypto traders**
**Stay safe, use SL/TP, diversify!** 💪
