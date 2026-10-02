# Intraday variance profile and variance time (generated 2026-10-02 22:22 UTC)

Binance BTC/USDT 1-minute returns, 2069 days (2021-01-01 to 2026-08-31); 1477 weekdays, 592 weekend days.

## Variance time of key windows (fraction of a day's expected variance)
```
         window  clock_fraction  all_days  weekday  weekend  weekday_robust  weekend_robust  weekday_us_summer  weekday_us_winter  weekday_5min  weekend_5min
08:00-17:00 UTC           0.375     0.423    0.438    0.359           0.448           0.355              0.443              0.430         0.450         0.355
08:00-16:00 UTC           0.333     0.370    0.383    0.309           0.389           0.305              0.392              0.371         0.396         0.305
08:00-22:00 UTC           0.583     0.658    0.674    0.588           0.684           0.584              0.672              0.676         0.678         0.585
08:00-21:00 UTC           0.542     0.611    0.627    0.539           0.643           0.529              0.623              0.633         0.633         0.534
```
Window meanings:
- 08:00-17:00 UTC: Deribit expiry -> noon New York in winter (EST)
- 08:00-16:00 UTC: Deribit expiry -> noon New York in summer (EDT)
- 08:00-22:00 UTC: Deribit expiry -> 17:00 New York in winter
- 08:00-21:00 UTC: Deribit expiry -> 17:00 New York in summer

## DST-matched: Deribit 08:00 UTC expiry -> Polymarket noon New York (weekdays)
```
                                           regime  variance_time  clock
US summer (EDT): 08:00 UTC -> noon NY = 16:00 UTC          0.392  0.333
US winter (EST): 08:00 UTC -> noon NY = 17:00 UTC          0.430  0.375
```

## Stability by year
```
      weekday_08-17  weekend_08-17  weekday_corr_with_pooled (hourly)  weekday_peak_hour_utc  weekday_peak/trough  days
2021          0.452          0.382                              0.893                     13                2.546   365
2022          0.413          0.353                              0.919                     13                3.099   365
2023          0.421          0.337                              0.901                     14                4.896   365
2024          0.435          0.303                              0.967                     14                3.867   366
2025          0.429          0.341                              0.931                     14                5.119   365
2026          0.469          0.314                              0.889                     14                4.464   243
```

## Daily variance level, weekend vs weekday (for horizons crossing midnight)
```
      weekend/weekday daily variance (mean)  weekend/weekday (median)
year                                                                 
2021                                  0.729                     0.648
2022                                  0.485                     0.559
2023                                  0.439                     0.399
2024                                  0.393                     0.363
2025                                  0.416                     0.355
2026                                  0.515                     0.427
all                                   0.559                     0.423
```

## Share of daily variance per UTC hour
```
     all_days  weekday  weekend  weekday_robust  weekend_robust  weekday_us_summer  weekday_us_winter  weekday_5min  weekend_5min
mod                                                                                                                              
0       0.048    0.047    0.049           0.047           0.055              0.050              0.044         0.048         0.049
1       0.041    0.042    0.035           0.043           0.043              0.044              0.039         0.041         0.033
2       0.033    0.033    0.029           0.034           0.036              0.033              0.034         0.033         0.028
3       0.030    0.028    0.040           0.027           0.031              0.027              0.030         0.027         0.051
4       0.027    0.026    0.032           0.024           0.029              0.026              0.026         0.027         0.039
5       0.031    0.025    0.058           0.023           0.031              0.025              0.024         0.024         0.043
6       0.029    0.029    0.030           0.025           0.027              0.030              0.026         0.028         0.035
7       0.028    0.028    0.029           0.027           0.028              0.029              0.027         0.029         0.030
8       0.033    0.033    0.035           0.031           0.032              0.031              0.035         0.034         0.037
9       0.033    0.032    0.038           0.029           0.032              0.029              0.036         0.033         0.036
10      0.031    0.030    0.037           0.027           0.031              0.028              0.033         0.030         0.038
11      0.031    0.030    0.034           0.028           0.032              0.031              0.029         0.031         0.034
12      0.049    0.051    0.041           0.047           0.037              0.058              0.042         0.055         0.041
13      0.064    0.069    0.039           0.068           0.042              0.082              0.052         0.072         0.038
14      0.068    0.074    0.042           0.085           0.050              0.073              0.077         0.076         0.040
15      0.060    0.064    0.044           0.072           0.050              0.061              0.068         0.064         0.042
16      0.054    0.055    0.050           0.059           0.050              0.052              0.059         0.054         0.050
17      0.048    0.049    0.043           0.052           0.045              0.048              0.050         0.046         0.044
18      0.047    0.048    0.043           0.050           0.043              0.048              0.048         0.046         0.041
19      0.045    0.046    0.038           0.048           0.040              0.043              0.052         0.046         0.038
20      0.048    0.046    0.056           0.045           0.045              0.041              0.053         0.045         0.057
21      0.047    0.047    0.049           0.041           0.056              0.049              0.044         0.045         0.051
22      0.042    0.038    0.060           0.036           0.072              0.034              0.044         0.037         0.058
23      0.034    0.031    0.049           0.029           0.063              0.031              0.031         0.029         0.049
```