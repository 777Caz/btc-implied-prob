# Phase 2 results (generated 2026-09-30 17:00 UTC)

Forecast origins 2021-03-24 to 2026-08-31 08:00 UTC; 1987 overlapping, 67 non-overlapping windows. Horizon 30 days. Outcome = Deribit delivery price.

## Volatility levels

```
                                 mean_annualised_vol_%  median_%
DVOL at origin                                 59.8670   55.4400
trailing 30d realised at origin                51.3773   49.7453
realised over the NEXT 30d                     51.0764   49.3931
```

## Breach table

```
                     sample model  band    side    n  expected  observed     se  p_value
        overlapping (daily)  dvol  5-95   below 1987    0.0500    0.0458 0.0175   0.8098
        overlapping (daily)  dvol  5-95   above 1987    0.0500    0.0825 0.0263   0.2159
        overlapping (daily)  dvol  5-95 outside 1987    0.1000    0.1283 0.0278   0.3074
        overlapping (daily)  dvol 10-90   below 1987    0.1000    0.0780 0.0253   0.3853
        overlapping (daily)  dvol 10-90   above 1987    0.1000    0.1213 0.0307   0.4885
        overlapping (daily)  dvol 10-90 outside 1987    0.2000    0.1993 0.0323   0.9826
        overlapping (daily)  dvol 25-75   below 1987    0.2500    0.1756 0.0367   0.0429
        overlapping (daily)  dvol 25-75   above 1987    0.2500    0.2682 0.0430   0.6714
        overlapping (daily)  dvol 25-75 outside 1987    0.5000    0.4439 0.0333   0.0917
        overlapping (daily)    rv  5-95   below 1987    0.0500    0.0876 0.0243   0.1228
        overlapping (daily)    rv  5-95   above 1987    0.0500    0.1047 0.0298   0.0661
        overlapping (daily)    rv  5-95 outside 1987    0.1000    0.1922 0.0315   0.0034
        overlapping (daily)    rv 10-90   below 1987    0.1000    0.1183 0.0308   0.5527
        overlapping (daily)    rv 10-90   above 1987    0.1000    0.1510 0.0337   0.1308
        overlapping (daily)    rv 10-90 outside 1987    0.2000    0.2693 0.0338   0.0404
        overlapping (daily)    rv 25-75   below 1987    0.2500    0.2028 0.0385   0.2202
        overlapping (daily)    rv 25-75   above 1987    0.2500    0.2798 0.0443   0.5013
        overlapping (daily)    rv 25-75 outside 1987    0.5000    0.4826 0.0315   0.5821
non-overlapping (every 30d)  dvol  5-95   below   67    0.0500    0.0448 0.0266   1.0000
non-overlapping (every 30d)  dvol  5-95   above   67    0.0500    0.0746 0.0266   0.3890
non-overlapping (every 30d)  dvol  5-95 outside   67    0.1000    0.1194 0.0367   0.5417
non-overlapping (every 30d)  dvol 10-90   below   67    0.1000    0.0746 0.0367   0.6823
non-overlapping (every 30d)  dvol 10-90   above   67    0.1000    0.1194 0.0367   0.5417
non-overlapping (every 30d)  dvol 10-90 outside   67    0.2000    0.1940 0.0489   1.0000
non-overlapping (every 30d)  dvol 25-75   below   67    0.2500    0.1493 0.0529   0.0657
non-overlapping (every 30d)  dvol 25-75   above   67    0.2500    0.2388 0.0529   1.0000
non-overlapping (every 30d)  dvol 25-75 outside   67    0.5000    0.3881 0.0611   0.0864
non-overlapping (every 30d)    rv  5-95   below   67    0.0500    0.0746 0.0266   0.3890
non-overlapping (every 30d)    rv  5-95   above   67    0.0500    0.1194 0.0266   0.0184
non-overlapping (every 30d)    rv  5-95 outside   67    0.1000    0.1940 0.0367   0.0217
non-overlapping (every 30d)    rv 10-90   below   67    0.1000    0.1045 0.0367   0.8386
non-overlapping (every 30d)    rv 10-90   above   67    0.1000    0.1493 0.0367   0.2162
non-overlapping (every 30d)    rv 10-90 outside   67    0.2000    0.2537 0.0489   0.2844
non-overlapping (every 30d)    rv 25-75   below   67    0.2500    0.1940 0.0529   0.3259
non-overlapping (every 30d)    rv 25-75   above   67    0.2500    0.2388 0.0529   1.0000
non-overlapping (every 30d)    rv 25-75 outside   67    0.5000    0.4328 0.0611   0.3284
```

## PIT tests

```
                     sample model    n  mean_pit  mean_pit_p  var_ratio  ks_stat   ks_p                                  ks_p_note
        overlapping (daily)  dvol 1987    0.5412      0.1974     0.9133   0.1016 0.1977 median over 30 non-overlapping sub-samples
        overlapping (daily)    rv 1987    0.5352      0.3098     1.0865   0.0648 0.4223 median over 30 non-overlapping sub-samples
non-overlapping (every 30d)  dvol   67    0.5390      0.2439     0.8881   0.1159 0.3053                                standard KS
non-overlapping (every 30d)    rv   67    0.5348      0.3375     1.0452   0.0970 0.5230                                standard KS
```

## Digital probabilities by strike

```
                     sample model strike    n  mean_forecast  observed  brier
        overlapping (daily)  dvol    80% 1987         0.8896    0.9170 0.0775
        overlapping (daily)  dvol    90% 1987         0.7160    0.7786 0.1748
        overlapping (daily)  dvol   100% 1987         0.4658    0.5199 0.2512
        overlapping (daily)  dvol   110% 1987         0.2468    0.2642 0.1985
        overlapping (daily)  dvol   120% 1987         0.1167    0.1339 0.1203
        overlapping (daily)    rv    80% 1987         0.9190    0.9170 0.0778
        overlapping (daily)    rv    90% 1987         0.7586    0.7786 0.1778
        overlapping (daily)    rv   100% 1987         0.4707    0.5199 0.2513
        overlapping (daily)    rv   110% 1987         0.2162    0.2642 0.2072
        overlapping (daily)    rv   120% 1987         0.0906    0.1339 0.1251
non-overlapping (every 30d)  dvol    80%   67         0.8847    0.9104 0.0872
non-overlapping (every 30d)  dvol    90%   67         0.7125    0.7761 0.1757
non-overlapping (every 30d)  dvol   100%   67         0.4650    0.5075 0.2493
non-overlapping (every 30d)  dvol   110%   67         0.2482    0.2537 0.1963
non-overlapping (every 30d)  dvol   120%   67         0.1194    0.1194 0.1093
non-overlapping (every 30d)    rv    80%   67         0.9162    0.9104 0.0876
non-overlapping (every 30d)    rv    90%   67         0.7549    0.7761 0.1772
non-overlapping (every 30d)    rv   100%   67         0.4703    0.5075 0.2488
non-overlapping (every 30d)    rv   110%   67         0.2187    0.2537 0.2049
non-overlapping (every 30d)    rv   120%   67         0.0933    0.1194 0.1119
```

## DVOL vs realised-vol baseline (loss differences)

```
                     sample                      metric   dvol     rv  mean_diff     se       z  p_value
        overlapping (daily)                   Brier 80% 0.0775 0.0778    -0.0003 0.0026 -0.1103   0.9121
        overlapping (daily)                   Brier 90% 0.1748 0.1778    -0.0029 0.0052 -0.5618   0.5742
        overlapping (daily)                  Brier 100% 0.2512 0.2513    -0.0000 0.0007 -0.0243   0.9806
        overlapping (daily)                  Brier 110% 0.1985 0.2072    -0.0087 0.0052 -1.6873   0.0916
        overlapping (daily)                  Brier 120% 0.1203 0.1251    -0.0048 0.0034 -1.4121   0.1579
        overlapping (daily)  Brier down tail (80%, 90%) 0.1262 0.1278    -0.0016 0.0036 -0.4485   0.6538
        overlapping (daily)  Brier up tail (110%, 120%) 0.1594 0.1662    -0.0068 0.0042 -1.6163   0.1060
        overlapping (daily)           Brier all strikes 0.1645 0.1678    -0.0034 0.0016 -2.1054   0.0353
        overlapping (daily) log score (higher = better) 0.3608 0.1323    -0.2285 0.0898 -2.5437   0.0110
non-overlapping (every 30d)                   Brier 80% 0.0872 0.0876    -0.0004 0.0041 -0.0902   0.9281
non-overlapping (every 30d)                   Brier 90% 0.1757 0.1772    -0.0015 0.0068 -0.2196   0.8262
non-overlapping (every 30d)                  Brier 100% 0.2493 0.2488     0.0004 0.0011  0.4082   0.6831
non-overlapping (every 30d)                  Brier 110% 0.1963 0.2049    -0.0086 0.0067 -1.2888   0.1975
non-overlapping (every 30d)                  Brier 120% 0.1093 0.1119    -0.0026 0.0041 -0.6343   0.5259
non-overlapping (every 30d)  Brier down tail (80%, 90%) 0.1314 0.1324    -0.0009 0.0047 -0.1957   0.8449
non-overlapping (every 30d)  Brier up tail (110%, 120%) 0.1528 0.1584    -0.0056 0.0049 -1.1526   0.2491
non-overlapping (every 30d)           Brier all strikes 0.1635 0.1661    -0.0025 0.0024 -1.0706   0.2843
non-overlapping (every 30d) log score (higher = better) 0.3165 0.1297    -0.1869 0.1057 -1.7674   0.0772
```

`compare`: mean_diff = loss(DVOL) - loss(RV); negative = DVOL better. For the log score the loss is minus the log score. p-values use Newey-West SEs (60 lags) in the overlapping sample.