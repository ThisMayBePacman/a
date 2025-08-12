# Trading Bot ATR-EMA Swing (Alpha)

**Bot de trading algorithmique modulaire et testable**, utilisant CCXT et basé sur les principes ATR-based SL/TP, stratégie multi-timeframe EMA/RSI/volume, gestion de risque, reprise d’état, et tests.

---

##  Fonctionnalités principales

-  Extraction via CCXT (Kraken Futures), récupération de bougies OHLCV flexibles.  
-  Stratégie swing multi-timeframe (M15 pour tendance, M5 pour signal) avec EMA, RSI, et filtre volume.  
-  SL/TP dynamiques basés sur ATR (SL = 1.5 × ATR, TP = 2 × ATR), suivi monotone, bump de TP paramétrable (`theta`, `rho`).  
-  Gestion de position robuste : market order, SL/TP bracket orders `reduceOnly`, alignement au tick, `watchdog` & `emergency_exit`.  
-  Reprise d’état intelligente via `load_active()` pour restaurer SL/TP.  
-  Tests complets (unitaires + property-based), typage Python (`mypy`), couvertures, design modulaire.

---

##  Installation

1. Clone ce dépôt  
   ```bash
   git clone https://github.com/ThisMayBePacman/a.git
   cd a
2. Crée un fichier .env à partir du modèle, renseigne tes clés API Kraken Futures :

    API_KEY=ta_clef_api
    API_SECRET=ton_secret
3. Installe les dépendances :

    pip install -r requirements.txt

##  Configuration (config.py)
| Paramètre                     | Description                       | Exemple                                              |
| ----------------------------- | --------------------------------- | ---------------------------------------------------- |
| `API_KEY`, `API_SECRET`       | Clés CCXT Kraken Futures          |                                                      |
| `SYMBOL`                      | ID du contrat (Kraken PF\_)       | `"PF_ETHUSD"`                                        |
| `INVESTMENT_USD`              | Capital investi (USD)             | `12`                                                 |
| `LEVERAGE`                    | Effet de levier                   | `8`                                                  |
| `TIMEFRAMES`                  | {"M15": "15m", "M5": "5m"}        |                                                      |
| `TICK_SIZE`                   | Tick minimal pour alignement prix | `0.5`                                                |
| `POLL_INTERVAL`               | Intervalle boucle (s)             | `10`                                                 |
| `STRATEGY`, `STRATEGY_PARAMS` | Trailing dynamique                | `"trailing_sl_and_tp"`, `{"theta": 0.5, "rho": 1.0}` |

Attention : Le fichier .env ne doit jamais être commité ! Il est exclu via .gitignore.

## Utilisation (Backtest, Paper, Live)
Actuellement, une seule exécution est disponible (main.py). Laisse STRATEGY=None pour le legacy trailing, ou configure la stratégie dans la config.

Plan futur :

    Ajouter mode backtest (sans exécution réelle, métriques, log CSV).

    Ajouter mode paper trading (simulé ORM/log).

    Mode live (exécution réelle avec protections reduceOnly, emergency exit, etc.).

## Architecture & Organisation
├── config.py               # Configuration + dotenv
├── data/fetcher.py         # CCXT + OHLCV → DataFrame
├── indicators/compute.py   # EMA, RSI, ATR, Vol_SMA
├── strategy/signal.py      # Logique swing multi-timeframe
├── risk/sl_tp.py           # Calcul SL/TP, alignements
├── risk/strategies/        # Base + Trailing dynamiques
├── execution/order_manager.py  # Envoi ordres + validation
├── execution/position_manager.py # Gestion position live et reload
├── utils/price_utils.py    # Alignement prix & quantité
├── utils/decorators.py     # Vérification `@verify_order`
├── tests/                  # Tests unitaires & propriété
└── main.py                 # Entrée principale (run)

## Attention et indemnité
Usage à vos risques : ce bot est destiné à l’éducation. Il n’est pas un produit de trading recommandé.

    Lance toujours en paper/training d’abord.

    Comprends chaque ligne, ajoute des logs structurés (id p.ex.).

    N’utilise jamais plus que tu ne peux te permettre de perdre.

    Ce projet n’est pas responsable de tes pertes ou erreurs de marché.

## Rejoindre le projet / Contribution
Contributions bienvenues : issues ou PR pour correction de bugs, création de stratégies, amélioration de CI, backtesting, etc.