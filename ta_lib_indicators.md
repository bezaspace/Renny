# TA-Lib Technical Analysis Indicators and Functions

Based on the documentation file `ta-lib-ta-lib-python-a2557b8d5a9637c8.txt`, TA-Lib provides a comprehensive set of technical analysis tools. The library includes **158 total functions**, categorized into 10 groups. While "indicators" typically refer to technical analysis indicators used in trading, TA-Lib also includes mathematical operators, transforms, and auxiliary functions.

The **total number of indicators/functions TA-Lib can analyze** is **158**.

Below is the complete list, organized by category as presented in the documentation. Indicators marked with (unstable) have an unstable initial period that should be considered when interpreting results.

## 1. Overlap Studies (17)
Trend-following and moving average indicators.

- BBANDS - Bollinger Bands
- DEMA - Double Exponential Moving Average
- EMA - Exponential Moving Average (unstable)
- HT_TRENDLINE - Hilbert Transform - Instantaneous Trendline (unstable)
- KAMA - Kaufman Adaptive Moving Average (unstable)
- MA - Moving average
- MAMA - MESA Adaptive Moving Average (unstable)
- MAVP - Moving average with variable period
- MIDPOINT - MidPoint over period
- MIDPRICE - Midpoint Price over period
- SAR - Parabolic SAR
- SAREXT - Parabolic SAR - Extended
- SMA - Simple Moving Average
- T3 - Triple Exponential Moving Average (T3) (unstable)
- TEMA - Triple Exponential Moving Average
- TRIMA - Triangular Moving Average
- WMA - Weighted Moving Average

## 2. Momentum Indicators (30)
Indicators measuring the speed and change of price movements.

- ADX - Average Directional Movement Index (unstable)
- ADXR - Average Directional Movement Index Rating (unstable)
- APO - Absolute Price Oscillator
- AROON - Aroon
- AROONOSC - Aroon Oscillator
- BOP - Balance Of Power
- CCI - Commodity Channel Index
- CMO - Chande Momentum Oscillator (unstable)
- DX - Directional Movement Index (unstable)
- MACD - Moving Average Convergence/Divergence
- MACDEXT - MACD with controllable MA type
- MACDFIX - Moving Average Convergence/Divergence Fix 12/26
- MFI - Money Flow Index (unstable)
- MINUS_DI - Minus Directional Indicator (unstable)
- MINUS_DM - Minus Directional Movement (unstable)
- MOM - Momentum
- PLUS_DI - Plus Directional Indicator (unstable)
- PLUS_DM - Plus Directional Movement (unstable)
- PPO - Percentage Price Oscillator
- ROC - Rate of change : ((price/prevPrice)-1)*100
- ROCP - Rate of change Percentage: (price-prevPrice)/prevPrice
- ROCR - Rate of change ratio: (price/prevPrice)
- ROCR100 - Rate of change ratio 100 scale: (price/prevPrice)*100
- RSI - Relative Strength Index (unstable)
- STOCH - Stochastic
- STOCHF - Stochastic Fast
- STOCHRSI - Stochastic Relative Strength Index (unstable)
- TRIX - 1-day Rate-Of-Change (ROC) of a Triple Smooth EMA
- ULTOSC - Ultimate Oscillator
- WILLR - Williams' %R

## 3. Volume Indicators (3)
Indicators that incorporate trading volume.

- AD - Chaikin A/D Line
- ADOSC - Chaikin A/D Oscillator
- OBV - On Balance Volume

## 4. Volatility Indicators (3)
Indicators measuring price volatility.

- ATR - Average True Range (unstable)
- NATR - Normalized Average True Range (unstable)
- TRANGE - True Range

## 5. Price Transform (4)
Functions that transform price data.

- AVGPRICE - Average Price
- MEDPRICE - Median Price
- TYPPRICE - Typical Price
- WCLPRICE - Weighted Close Price

## 6. Cycle Indicators (5)
Indicators detecting cyclical components using Hilbert transform.

- HT_DCPERIOD - Hilbert Transform - Dominant Cycle Period (unstable)
- HT_DCPHASE - Hilbert Transform - Dominant Cycle Phase (unstable)
- HT_PHASOR - Hilbert Transform - Phasor Components (unstable)
- HT_SINE - Hilbert Transform - SineWave (unstable)
- HT_TRENDMODE - Hilbert Transform - Trend vs Cycle Mode (unstable)

## 7. Pattern Recognition (61)
Candlestick pattern recognition functions. Each returns an integer signal (bullish/bearish/neutral).

- CDL2CROWS - Two Crows
- CDL3BLACKCROWS - Three Black Crows
- CDL3INSIDE - Three Inside Up/Down
- CDL3LINESTRIKE - Three-Line Strike
- CDL3OUTSIDE - Three Outside Up/Down
- CDL3STARSINSOUTH - Three Stars In The South
- CDL3WHITESOLDIERS - Three Advancing White Soldiers
- CDLABANDONEDBABY - Abandoned Baby
- CDLADVANCEBLOCK - Advance Block
- CDLBELTHOLD - Belt-hold
- CDLBREAKAWAY - Breakaway
- CDLCLOSINGMARUBOZU - Closing Marubozu
- CDLCONCEALBABYSWALL - Concealing Baby Swallow
- CDLCOUNTERATTACK - Counterattack
- CDLDARKCLOUDCOVER - Dark Cloud Cover
- CDLDOJI - Doji
- CDLDOJISTAR - Doji Star
- CDLDRAGONFLYDOJI - Dragonfly Doji
- CDLENGULFING - Engulfing Pattern
- CDLEVENINGDOJISTAR - Evening Doji Star
- CDLEVENINGSTAR - Evening Star
- CDLGAPSIDESIDEWHITE - Up/Down-gap side-by-side white lines
- CDLGRAVESTONEDOJI - Gravestone Doji
- CDLHAMMER - Hammer
- CDLHANGINGMAN - Hanging Man
- CDLHARAMI - Harami Pattern
- CDLHARAMICROSS - Harami Cross Pattern
- CDLHIGHWAVE - High-Wave Candle
- CDLHIKKAKE - Hikkake Pattern
- CDLHIKKAKEMOD - Modified Hikkake Pattern
- CDLHOMINGPIGEON - Homing Pigeon
- CDLIDENTICAL3CROWS - Identical Three Crows
- CDLINNECK - In-Neck Pattern
- CDLINVERTEDHAMMER - Inverted Hammer
- CDLKICKING - Kicking
- CDLKICKINGBYLENGTH - Kicking - bull/bear determined by the longer marubozu
- CDLLADDERBOTTOM - Ladder Bottom
- CDLLONGLEGGEDDOJI - Long Legged Doji
- CDLLONGLINE - Long Line Candle
- CDLMARUBOZU - Marubozu
- CDLMATCHINGLOW - Matching Low
- CDLMATHOLD - Mat Hold
- CDLMORNINGDOJISTAR - Morning Doji Star
- CDLMORNINGSTAR - Morning Star
- CDLONNECK - On-Neck Pattern
- CDLPIERCING - Piercing Pattern
- CDLRICKSHAWMAN - Rickshaw Man
- CDLRISEFALL3METHODS - Rising/Falling Three Methods
- CDLSEPARATINGLINES - Separating Lines
- CDLSHOOTINGSTAR - Shooting Star
- CDLSHORTLINE - Short Line Candle
- CDLSPINNINGTOP - Spinning Top
- CDLSTALLEDPATTERN - Stalled Pattern
- CDLSTICKSANDWICH - Stick Sandwich
- CDLTAKURI - Takuri (Dragonfly Doji with very long lower shadow)
- CDLTASUKIGAP - Tasuki Gap
- CDLTHRUSTING - Thrusting Pattern
- CDLTRISTAR - Tristar Pattern
- CDLUNIQUE3RIVER - Unique 3 River
- CDLUPSIDEGAP2CROWS - Upside Gap Two Crows
- CDLXSIDEGAP3METHODS - Upside/Downside Gap Three Methods

## 8. Statistic Functions (9)
Statistical and mathematical analysis functions.

- BETA - Beta
- CORREL - Pearson's Correlation Coefficient (r)
- LINEARREG - Linear Regression
- LINEARREG_ANGLE - Linear Regression Angle
- LINEARREG_INTERCEPT - Linear Regression Intercept
- LINEARREG_SLOPE - Linear Regression Slope
- STDDEV - Standard Deviation
- TSF - Time Series Forecast
- VAR - Variance

## 9. Math Transform (15)
Mathematical transformation functions applied to input arrays.

- ACOS - Vector Trigonometric ACos
- ASIN - Vector Trigonometric ASin
- ATAN - Vector Trigonometric ATan
- CEIL - Vector Ceil
- COS - Vector Trigonometric Cos
- COSH - Vector Trigonometric Cosh
- EXP - Vector Arithmetic Exp
- FLOOR - Vector Floor
- LN - Vector Log Natural
- LOG10 - Vector Log10
- SIN - Vector Trigonometric Sin
- SINH - Vector Trigonometric Sinh
- SQRT - Vector Square Root
- TAN - Vector Trigonometric Tan
- TANH - Vector Trigonometric Tanh

## 10. Math Operators (11)
Basic mathematical operations on vectors.

- ADD - Vector Arithmetic Add
- DIV - Vector Arithmetic Div
- MAX - Highest value over a specified period
- MAXINDEX - Index of highest value over a specified period
- MIN - Lowest value over a specified period
- MININDEX - Index of lowest value over a specified period
- MINMAX - Lowest and highest values over a specified period
- MINMAXINDEX - Indexes of lowest and highest values over a specified period
- MULT - Vector Arithmetic Mult
- SUB - Vector Arithmetic Subtraction
- SUM - Summation

## Summary
- **Total Functions:** 158
- **Type Distribution:**
  - Technical Indicators: 125 (Overlap + Momentum + Volume + Volatility + Price Transform + Cycle + Statistic + Pattern Recognition)
  - Candlestick Patterns: 61
  - Mathematical Utilities: 26 (Math Transform + Math Operators)

## Notes
- Functions marked with "(unstable)" have an initial period where results may be unreliable
- All functions require appropriate input data (OHLC, volume, etc.) depending on their requirements
- Pattern recognition functions return integer values indicating bullish/bearish/neutral signals
- TA-Lib is widely used for automated trading systems, technical analysis, and financial research
