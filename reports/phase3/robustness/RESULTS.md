# Phase 3 robustness (generated 2026-10-02 21:13 UTC)

## 1. Parity forward vs Deribit futures, by tenor
```
        comparisons  days  median_abs_bps  p90_abs_bps  mean_bps  median_bps
tenor                                                                       
<7d             149   145           2.628        7.430     1.407       1.203
7-30d           194   141           3.012        8.146     0.486       0.371
30-90d          107    93           3.998       11.984     1.782       0.687
90d+             39    37           4.246       16.906     2.431       2.103
```
Slope of signed error vs tenor: 4.19 bp per year of tenor.

## 2. Discounting test (c - p = DF (1 - K/F)) on live snapshots
```
                   fits  median_days  median_DF_minus_1_bps  p10_bps  p90_bps  median_implied_rate_pct  interest_rate_field
prices     tenor                                                                                                           
mark_price <7d      117        2.701                 -0.014   -1.403    1.946                    0.030                0.000
           7-30d     97       20.514                  0.031   -0.335    1.270                   -0.006                0.000
           30-90d    64       70.564                  0.073   -0.640    1.950                   -0.004                0.000
           90d+      96      265.705                  0.060   -0.753    2.198                   -0.001                0.000
mid        <7d      117        2.701                 -5.245  -15.572    7.642                    5.105                0.000
           7-30d     97       20.514                 -0.655   -5.932    4.079                    0.117                0.000
           30-90d    64       70.564                 -1.627   -6.680    2.882                    0.077                0.000
           90d+      96      265.705                  1.025  -12.423   27.516                   -0.017                0.000
```

## 3. Look-ahead audit (all months)
```
origins                                             2099
latest_trade_minus_origin       -1 days +23:59:59.997000
earliest_trade_before_origin      0 days 07:59:59.998000
trades_with_expiry_within_1d                           0
```

## 4. Tail breaches by origin year (30-day block bootstrap 95% CI)
```
model                           dvol    rv  smile
tail           period                            
above 95th pct 2021              3.8   6.4    6.4
               2022              2.1   3.9    3.0
               2023             13.0  15.9   14.7
               2024             17.5  20.2   16.9
               2025              1.1   2.2    1.7
               2026              9.0  10.8    9.9
               all               7.9  10.0    8.8
               all except 2022   9.1  11.4   10.1
below 5th pct  2021              4.2   9.1    4.2
               2022              6.0  14.1    3.6
               2023              0.0   6.1    0.0
               2024              0.0   1.1    0.3
               2025              3.0   4.4    2.5
               2026             19.7  23.8   18.4
               all               4.5   8.7    3.9
               all except 2022   4.2   7.6    4.0
```

## 5. EXPLORATORY option test (every 30 days, half-spread 1.00 vol pts; 2026 snapshot quotes (544): median 0.53, p90 0.72)

P&L in % of S0 per 1 BTC notional (return on premium for the last row).
```
                                  trades   mean  mean_ci_lo  mean_ci_hi  median  hit_rate  hit_ci_lo  hit_ci_hi   total   worst   best
strategy                                                                                                                              
long 25d call                         58 -0.254      -1.737       1.489  -2.316     0.138      0.052      0.224 -14.749  -3.760 22.002
long 25d call, no costs               58 -0.129      -1.603       1.636  -2.187     0.138      0.052      0.241  -7.461  -3.627 22.147
25d risk reversal                     58  0.469      -1.703       2.688   0.267     0.672      0.552      0.793  27.192 -25.817 24.828
25d risk reversal, no costs           58  0.718      -1.522       2.952   0.526     0.724      0.603      0.828  41.635 -25.584 25.101
long 25d call, return on premium      58 -0.046      -0.642       0.687  -1.000     0.138      0.052      0.224  -2.659  -1.000 11.263
```

Spread sensitivity (mean P&L % of S0 and hit rate):
```
                                    mean  mean_ci_lo  mean_ci_hi  hit_rate
half_spread_vol strategy                                                  
0.00            long 25d call     -0.162      -1.623       1.608     0.138
                25d risk reversal  0.651      -1.504       2.862     0.724
0.72            long 25d call     -0.229      -1.655       1.522     0.138
                25d risk reversal  0.520      -1.690       2.802     0.672
1.00            long 25d call     -0.254      -1.719       1.473     0.138
                25d risk reversal  0.469      -1.718       2.753     0.672
2.00            long 25d call     -0.347      -1.771       1.399     0.138
                25d risk reversal  0.286      -1.882       2.533     0.586
```

Across the 30 possible start days:
```
      trades  call_mean  rr_mean  call_hit  rr_hit
mean  58.133     -0.037    0.480     0.162   0.598
min   52.000     -0.639   -0.158     0.125   0.517
max   61.000      0.883    1.639     0.217   0.683
```