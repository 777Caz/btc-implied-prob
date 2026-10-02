# Phase 3 results (generated 2026-10-02 19:20 UTC)

Origins with a smile-based 30-day distribution (and DVOL + RV): 1892 overlapping, 64 non-overlapping, 2021-03-24 to 2026-08-31.

## fit_status

```
                    expiry_days  share_%
status                                  
ok                        15729  84.7103
few trades                 1851   9.9688
no forward                  831   4.4754
few strikes                  74   0.3985
one-sided strikes            46   0.2477
fit failed                   35   0.1885
narrow strike span            2   0.0108
```

## fit_quality

```
 expiry_days_fitted  rmse_vol_pts_median  rmse_vol_pts_p90  butterfly_arb  vertical_arb  calendar_arb_with_next  forward_from_parity_%
              15729               0.5042            1.4428            691           164                     127                46.8371
```

## breach

```
                     sample model  band    side    n  expected  observed     se  p_value
        overlapping (daily) smile  5-95   below 1892    0.0500    0.0391 0.0153   0.4756
        overlapping (daily) smile  5-95   above 1892    0.0500    0.0883 0.0257   0.1360
        overlapping (daily) smile  5-95 outside 1892    0.1000    0.1274 0.0261   0.2941
        overlapping (daily) smile 10-90   below 1892    0.1000    0.0999 0.0280   0.9970
        overlapping (daily) smile 10-90   above 1892    0.1000    0.1311 0.0313   0.3202
        overlapping (daily) smile 10-90 outside 1892    0.2000    0.2310 0.0323   0.3376
        overlapping (daily) smile 25-75   below 1892    0.2500    0.2141 0.0390   0.3567
        overlapping (daily) smile 25-75   above 1892    0.2500    0.2807 0.0446   0.4920
        overlapping (daily) smile 25-75 outside 1892    0.5000    0.4947 0.0312   0.8654
        overlapping (daily)  dvol  5-95   below 1892    0.0500    0.0455 0.0173   0.7923
        overlapping (daily)  dvol  5-95   above 1892    0.0500    0.0788 0.0257   0.2634
        overlapping (daily)  dvol  5-95 outside 1892    0.1000    0.1242 0.0271   0.3723
        overlapping (daily)  dvol 10-90   below 1892    0.1000    0.0772 0.0248   0.3576
        overlapping (daily)  dvol 10-90   above 1892    0.1000    0.1163 0.0300   0.5868
        overlapping (daily)  dvol 10-90 outside 1892    0.2000    0.1934 0.0314   0.8349
        overlapping (daily)  dvol 25-75   below 1892    0.2500    0.1765 0.0365   0.0443
        overlapping (daily)  dvol 25-75   above 1892    0.2500    0.2669 0.0430   0.6943
        overlapping (daily)  dvol 25-75 outside 1892    0.5000    0.4434 0.0333   0.0892
        overlapping (daily)    rv  5-95   below 1892    0.0500    0.0872 0.0242   0.1246
        overlapping (daily)    rv  5-95   above 1892    0.0500    0.1004 0.0290   0.0819
        overlapping (daily)    rv  5-95 outside 1892    0.1000    0.1876 0.0310   0.0047
        overlapping (daily)    rv 10-90   below 1892    0.1000    0.1179 0.0304   0.5569
        overlapping (daily)    rv 10-90   above 1892    0.1000    0.1469 0.0332   0.1575
        overlapping (daily)    rv 10-90 outside 1892    0.2000    0.2648 0.0334   0.0521
        overlapping (daily)    rv 25-75   below 1892    0.2500    0.2030 0.0382   0.2185
        overlapping (daily)    rv 25-75   above 1892    0.2500    0.2791 0.0445   0.5132
        overlapping (daily)    rv 25-75 outside 1892    0.5000    0.4820 0.0317   0.5713
        overlapping (daily)   atm  5-95   below 1892    0.0500    0.0597 0.0210   0.6440
        overlapping (daily)   atm  5-95   above 1892    0.0500    0.0840 0.0256   0.1844
        overlapping (daily)   atm  5-95 outside 1892    0.1000    0.1438 0.0281   0.1195
        overlapping (daily)   atm 10-90   below 1892    0.1000    0.0957 0.0280   0.8769
        overlapping (daily)   atm 10-90   above 1892    0.1000    0.1216 0.0304   0.4781
        overlapping (daily)   atm 10-90 outside 1892    0.2000    0.2172 0.0324   0.5950
        overlapping (daily)   atm 25-75   below 1892    0.2500    0.1966 0.0380   0.1605
        overlapping (daily)   atm 25-75   above 1892    0.2500    0.2685 0.0430   0.6670
        overlapping (daily)   atm 25-75 outside 1892    0.5000    0.4651 0.0324   0.2823
non-overlapping (every 30d) smile  5-95   below   64    0.0500    0.0156 0.0272   0.3796
non-overlapping (every 30d) smile  5-95   above   64    0.0500    0.1094 0.0272   0.0403
non-overlapping (every 30d) smile  5-95 outside   64    0.1000    0.1250 0.0375   0.5283
non-overlapping (every 30d) smile 10-90   below   64    0.1000    0.0625 0.0375   0.4071
non-overlapping (every 30d) smile 10-90   above   64    0.1000    0.1719 0.0375   0.0611
non-overlapping (every 30d) smile 10-90 outside   64    0.2000    0.2344 0.0500   0.5311
non-overlapping (every 30d) smile 25-75   below   64    0.2500    0.2188 0.0541   0.6655
non-overlapping (every 30d) smile 25-75   above   64    0.2500    0.2656 0.0541   0.7733
non-overlapping (every 30d) smile 25-75 outside   64    0.5000    0.4844 0.0625   0.9007
non-overlapping (every 30d)  dvol  5-95   below   64    0.0500    0.0312 0.0272   0.7721
non-overlapping (every 30d)  dvol  5-95   above   64    0.0500    0.0781 0.0272   0.2532
non-overlapping (every 30d)  dvol  5-95 outside   64    0.1000    0.1094 0.0375   0.8337
non-overlapping (every 30d)  dvol 10-90   below   64    0.1000    0.0625 0.0375   0.4071
non-overlapping (every 30d)  dvol 10-90   above   64    0.1000    0.1562 0.0375   0.1417
non-overlapping (every 30d)  dvol 10-90 outside   64    0.2000    0.2188 0.0500   0.7542
non-overlapping (every 30d)  dvol 25-75   below   64    0.2500    0.1562 0.0541   0.1108
non-overlapping (every 30d)  dvol 25-75   above   64    0.2500    0.2500 0.0541   1.0000
non-overlapping (every 30d)  dvol 25-75 outside   64    0.5000    0.4062 0.0625   0.1686
non-overlapping (every 30d)    rv  5-95   below   64    0.0500    0.0781 0.0272   0.2532
non-overlapping (every 30d)    rv  5-95   above   64    0.0500    0.1250 0.0272   0.0142
non-overlapping (every 30d)    rv  5-95 outside   64    0.1000    0.2031 0.0375   0.0111
non-overlapping (every 30d)    rv 10-90   below   64    0.1000    0.1250 0.0375   0.5283
non-overlapping (every 30d)    rv 10-90   above   64    0.1000    0.1562 0.0375   0.1417
non-overlapping (every 30d)    rv 10-90 outside   64    0.2000    0.2812 0.0500   0.1170
non-overlapping (every 30d)    rv 25-75   below   64    0.2500    0.1875 0.0541   0.3119
non-overlapping (every 30d)    rv 25-75   above   64    0.2500    0.2500 0.0541   1.0000
non-overlapping (every 30d)    rv 25-75 outside   64    0.5000    0.4375 0.0625   0.3817
non-overlapping (every 30d)   atm  5-95   below   64    0.0500    0.0469 0.0272   1.0000
non-overlapping (every 30d)   atm  5-95   above   64    0.0500    0.1094 0.0272   0.0403
non-overlapping (every 30d)   atm  5-95 outside   64    0.1000    0.1562 0.0375   0.1417
non-overlapping (every 30d)   atm 10-90   below   64    0.1000    0.0781 0.0375   0.6805
non-overlapping (every 30d)   atm 10-90   above   64    0.1000    0.1562 0.0375   0.1417
non-overlapping (every 30d)   atm 10-90 outside   64    0.2000    0.2344 0.0500   0.5311
non-overlapping (every 30d)   atm 25-75   below   64    0.2500    0.1719 0.0541   0.1928
non-overlapping (every 30d)   atm 25-75   above   64    0.2500    0.2500 0.0541   1.0000
non-overlapping (every 30d)   atm 25-75 outside   64    0.5000    0.4219 0.0625   0.2604
```

## pit

```
                     sample model    n  mean_pit  mean_pit_p  var_ratio  ks_stat   ks_p                                  ks_p_note
        overlapping (daily) smile 1892    0.5222      0.5116     1.0206   0.0480 0.7515 median over 30 non-overlapping sub-samples
        overlapping (daily)  dvol 1892    0.5398      0.2105     0.9087   0.0997 0.2382 median over 30 non-overlapping sub-samples
        overlapping (daily)    rv 1892    0.5340      0.3242     1.0829   0.0617 0.4692 median over 30 non-overlapping sub-samples
        overlapping (daily)   atm 1892    0.5290      0.3778     0.9816   0.0756 0.4944 median over 30 non-overlapping sub-samples
non-overlapping (every 30d) smile   64    0.5129      0.7229     1.0042   0.0799 0.7786                                standard KS
non-overlapping (every 30d)  dvol   64    0.5359      0.2916     0.8773   0.1335 0.1867                                standard KS
non-overlapping (every 30d)    rv   64    0.5219      0.5598     1.0661   0.0971 0.5493                                standard KS
non-overlapping (every 30d)   atm   64    0.5232      0.5169     0.9654   0.0979 0.5391                                standard KS
```

## digital

```
                     sample model strike    n  mean_forecast  observed  brier
        overlapping (daily) smile    80% 1892         0.9095    0.9181 0.0749
        overlapping (daily) smile    90% 1892         0.7696    0.7770 0.1712
        overlapping (daily) smile   100% 1892         0.4976    0.5201 0.2497
        overlapping (daily) smile   110% 1892         0.2335    0.2622 0.2010
        overlapping (daily) smile   120% 1892         0.1007    0.1295 0.1167
        overlapping (daily)  dvol    80% 1892         0.8902    0.9181 0.0764
        overlapping (daily)  dvol    90% 1892         0.7164    0.7770 0.1748
        overlapping (daily)  dvol   100% 1892         0.4659    0.5201 0.2512
        overlapping (daily)  dvol   110% 1892         0.2466    0.2622 0.1972
        overlapping (daily)  dvol   120% 1892         0.1164    0.1295 0.1165
        overlapping (daily)    rv    80% 1892         0.9193    0.9181 0.0765
        overlapping (daily)    rv    90% 1892         0.7587    0.7770 0.1779
        overlapping (daily)    rv   100% 1892         0.4707    0.5201 0.2512
        overlapping (daily)    rv   110% 1892         0.2161    0.2622 0.2055
        overlapping (daily)    rv   120% 1892         0.0904    0.1295 0.1209
        overlapping (daily)   atm    80% 1892         0.9101    0.9181 0.0760
        overlapping (daily)   atm    90% 1892         0.7422    0.7770 0.1728
        overlapping (daily)   atm   100% 1892         0.4805    0.5201 0.2515
        overlapping (daily)   atm   110% 1892         0.2458    0.2622 0.1987
        overlapping (daily)   atm   120% 1892         0.1099    0.1295 0.1171
non-overlapping (every 30d) smile    80%   64         0.9068    0.9219 0.0697
non-overlapping (every 30d) smile    90%   64         0.7683    0.7656 0.1686
non-overlapping (every 30d) smile   100%   64         0.4982    0.5000 0.2518
non-overlapping (every 30d) smile   110%   64         0.2363    0.2656 0.2004
non-overlapping (every 30d) smile   120%   64         0.1030    0.1406 0.1270
non-overlapping (every 30d)  dvol    80%   64         0.8876    0.9219 0.0704
non-overlapping (every 30d)  dvol    90%   64         0.7153    0.7656 0.1658
non-overlapping (every 30d)  dvol   100%   64         0.4654    0.5000 0.2501
non-overlapping (every 30d)  dvol   110%   64         0.2466    0.2656 0.1971
non-overlapping (every 30d)  dvol   120%   64         0.1174    0.1406 0.1258
non-overlapping (every 30d)    rv    80%   64         0.9160    0.9219 0.0752
non-overlapping (every 30d)    rv    90%   64         0.7549    0.7656 0.1735
non-overlapping (every 30d)    rv   100%   64         0.4702    0.5000 0.2515
non-overlapping (every 30d)    rv   110%   64         0.2186    0.2656 0.2076
non-overlapping (every 30d)    rv   120%   64         0.0931    0.1406 0.1323
non-overlapping (every 30d)   atm    80%   64         0.9066    0.9219 0.0702
non-overlapping (every 30d)   atm    90%   64         0.7397    0.7656 0.1670
non-overlapping (every 30d)   atm   100%   64         0.4799    0.5000 0.2535
non-overlapping (every 30d)   atm   110%   64         0.2464    0.2656 0.1979
non-overlapping (every 30d)   atm   120%   64         0.1113    0.1406 0.1268
```

## compare

```
                     sample   vs                      metric  smile  other  mean_diff     se       z  p_value
        overlapping (daily) dvol                   Brier 80% 0.0749 0.0764    -0.0014 0.0021 -0.6832   0.4945
        overlapping (daily) dvol                   Brier 90% 0.1712 0.1748    -0.0036 0.0044 -0.8216   0.4113
        overlapping (daily) dvol                  Brier 100% 0.2497 0.2512    -0.0015 0.0033 -0.4682   0.6396
        overlapping (daily) dvol                  Brier 110% 0.2010 0.1972     0.0038 0.0021  1.8409   0.0656
        overlapping (daily) dvol                  Brier 120% 0.1167 0.1165     0.0002 0.0011  0.1888   0.8503
        overlapping (daily) dvol  Brier down tail (80%, 90%) 0.1231 0.1256    -0.0025 0.0030 -0.8280   0.4077
        overlapping (daily) dvol  Brier up tail (110%, 120%) 0.1588 0.1568     0.0020 0.0014  1.4344   0.1515
        overlapping (daily) dvol           Brier all strikes 0.1627 0.1632    -0.0005 0.0016 -0.3286   0.7425
        overlapping (daily) dvol log score (higher = better) 0.3786 0.3692    -0.0094 0.0196 -0.4773   0.6331
        overlapping (daily)   rv                   Brier 80% 0.0749 0.0765    -0.0015 0.0020 -0.7711   0.4407
        overlapping (daily)   rv                   Brier 90% 0.1712 0.1779    -0.0066 0.0040 -1.6672   0.0955
        overlapping (daily)   rv                  Brier 100% 0.2497 0.2512    -0.0015 0.0029 -0.5270   0.5982
        overlapping (daily)   rv                  Brier 110% 0.2010 0.2055    -0.0045 0.0039 -1.1381   0.2551
        overlapping (daily)   rv                  Brier 120% 0.1167 0.1209    -0.0043 0.0030 -1.4248   0.1542
        overlapping (daily)   rv  Brier down tail (80%, 90%) 0.1231 0.1272    -0.0041 0.0028 -1.4768   0.1397
        overlapping (daily)   rv  Brier up tail (110%, 120%) 0.1588 0.1632    -0.0044 0.0034 -1.2862   0.1984
        overlapping (daily)   rv           Brier all strikes 0.1627 0.1664    -0.0037 0.0019 -1.8936   0.0583
        overlapping (daily)   rv log score (higher = better) 0.3786 0.1553    -0.2233 0.0871 -2.5634   0.0104
        overlapping (daily)  atm                   Brier 80% 0.0749 0.0760    -0.0010 0.0006 -1.6468   0.0996
        overlapping (daily)  atm                   Brier 90% 0.1712 0.1728    -0.0016 0.0023 -0.6891   0.4908
        overlapping (daily)  atm                  Brier 100% 0.2497 0.2515    -0.0018 0.0023 -0.7862   0.4317
        overlapping (daily)  atm                  Brier 110% 0.2010 0.1987     0.0023 0.0018  1.3031   0.1925
        overlapping (daily)  atm                  Brier 120% 0.1167 0.1171    -0.0005 0.0006 -0.7904   0.4293
        overlapping (daily)  atm  Brier down tail (80%, 90%) 0.1231 0.1244    -0.0013 0.0013 -1.0252   0.3053
        overlapping (daily)  atm  Brier up tail (110%, 120%) 0.1588 0.1579     0.0009 0.0010  0.9305   0.3521
        overlapping (daily)  atm           Brier all strikes 0.1627 0.1632    -0.0005 0.0008 -0.6203   0.5351
        overlapping (daily)  atm log score (higher = better) 0.3786 0.3578    -0.0208 0.0179 -1.1617   0.2454
non-overlapping (every 30d) dvol                   Brier 80% 0.0697 0.0704    -0.0007 0.0034 -0.2076   0.8356
non-overlapping (every 30d) dvol                   Brier 90% 0.1686 0.1658     0.0028 0.0068  0.4075   0.6836
non-overlapping (every 30d) dvol                  Brier 100% 0.2518 0.2501     0.0017 0.0048  0.3533   0.7238
non-overlapping (every 30d) dvol                  Brier 110% 0.2004 0.1971     0.0033 0.0025  1.2976   0.1944
non-overlapping (every 30d) dvol                  Brier 120% 0.1270 0.1258     0.0012 0.0019  0.6155   0.5382
non-overlapping (every 30d) dvol  Brier down tail (80%, 90%) 0.1191 0.1181     0.0010 0.0043  0.2384   0.8116
non-overlapping (every 30d) dvol  Brier up tail (110%, 120%) 0.1637 0.1615     0.0022 0.0020  1.1189   0.2632
non-overlapping (every 30d) dvol           Brier all strikes 0.1635 0.1618     0.0016 0.0024  0.6757   0.4992
non-overlapping (every 30d) dvol log score (higher = better) 0.3721 0.3704    -0.0018 0.0336 -0.0524   0.9582
non-overlapping (every 30d)   rv                   Brier 80% 0.0697 0.0752    -0.0055 0.0036 -1.5287   0.1263
non-overlapping (every 30d)   rv                   Brier 90% 0.1686 0.1735    -0.0049 0.0064 -0.7726   0.4398
non-overlapping (every 30d)   rv                  Brier 100% 0.2518 0.2515     0.0003 0.0044  0.0575   0.9541
non-overlapping (every 30d)   rv                  Brier 110% 0.2004 0.2076    -0.0072 0.0049 -1.4772   0.1396
non-overlapping (every 30d)   rv                  Brier 120% 0.1270 0.1323    -0.0053 0.0038 -1.4078   0.1592
non-overlapping (every 30d)   rv  Brier down tail (80%, 90%) 0.1191 0.1243    -0.0052 0.0041 -1.2704   0.2039
non-overlapping (every 30d)   rv  Brier up tail (110%, 120%) 0.1637 0.1700    -0.0063 0.0041 -1.5419   0.1231
non-overlapping (every 30d)   rv           Brier all strikes 0.1635 0.1680    -0.0046 0.0026 -1.7678   0.0771
non-overlapping (every 30d)   rv log score (higher = better) 0.3721 0.0679    -0.3043 0.1349 -2.2549   0.0241
non-overlapping (every 30d)  atm                   Brier 80% 0.0697 0.0702    -0.0005 0.0012 -0.4642   0.6425
non-overlapping (every 30d)  atm                   Brier 90% 0.1686 0.1670     0.0016 0.0039  0.4103   0.6816
non-overlapping (every 30d)  atm                  Brier 100% 0.2518 0.2535    -0.0017 0.0036 -0.4731   0.6362
non-overlapping (every 30d)  atm                  Brier 110% 0.2004 0.1979     0.0025 0.0022  1.1480   0.2510
non-overlapping (every 30d)  atm                  Brier 120% 0.1270 0.1268     0.0002 0.0010  0.1818   0.8557
non-overlapping (every 30d)  atm  Brier down tail (80%, 90%) 0.1191 0.1186     0.0005 0.0022  0.2395   0.8107
non-overlapping (every 30d)  atm  Brier up tail (110%, 120%) 0.1637 0.1623     0.0014 0.0013  1.0084   0.3133
non-overlapping (every 30d)  atm           Brier all strikes 0.1635 0.1631     0.0004 0.0016  0.2684   0.7884
non-overlapping (every 30d)  atm log score (higher = better) 0.3721 0.3615    -0.0107 0.0305 -0.3493   0.7269
```
