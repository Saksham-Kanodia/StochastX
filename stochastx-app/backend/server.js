const express = require("express");
const cors = require("cors");
const { exec } = require("child_process");
const path = require("path");
const fs = require("fs");

const app = express();
app.use(cors());
app.use(express.json());

const PORT = 5000;

app.get("/api/assets", (req, res) => {
  const csvPath = path.join(__dirname, "nse_5yr_data.csv");
  fs.readFile(csvPath, "utf8", (err, data) => {
    if (err) return res.status(500).json({ error: "Failed to read CSV dataset file." });
    const firstLine = data.split("\n")[0];
    const columns = firstLine.split(",").map(c => c.trim().replace(/"/g, "")).filter(c => c !== "Date" && c !== "");
    res.json(columns);
  });
});

app.get("/api/backtest", (req, res) => {
  const asset = req.query.asset || "AXISBANK.NS";
  const deriskFactor = parseFloat(req.query.derisk) || 0.4;
  const csvPath = path.join(__dirname, "nse_5yr_data.csv");

  exec(`python gmm_bridge.py "${csvPath}" "${asset}"`, { maxBuffer: 1024 * 1024 * 10 }, (error, stdout) => {
    if (error) return res.status(500).json({ error: "GMM Python Execution Failed." });

    try {
      const parsed = JSON.parse(stdout);
      if (parsed.error) return res.status(400).json({ error: parsed.error });

      const { dates, prices, regimes } = parsed;
      let staticCapital = 100000;
      let dynamicCapital = 100000;
      
      const chartData = [];
      let staticPeak = staticCapital;
      let dynamicPeak = dynamicCapital;
      let staticMaxDD = 0;
      let dynamicMaxDD = 0;

      const dynamicReturnsList = [];
      const staticReturnsList = [];

      for (let i = 1; i < prices.length; i++) {
        const rawReturn = (prices[i] - prices[i - 1]) / prices[i - 1];
        const isTurbulent = regimes[i].includes("High Volatility");
        
        const exposure = isTurbulent ? deriskFactor : 1.0;
        
        const staticRet = rawReturn;
        const dynamicRet = rawReturn * exposure;

        staticCapital *= (1 + staticRet);
        dynamicCapital *= (1 + dynamicRet);

        staticReturnsList.push(staticRet);
        dynamicReturnsList.push(dynamicRet);

        if (staticCapital > staticPeak) staticPeak = staticCapital;
        if (dynamicCapital > dynamicPeak) dynamicPeak = dynamicCapital;

        const currentStaticDD = (staticPeak - staticCapital) / staticPeak;
        const currentDynamicDD = (dynamicPeak - dynamicCapital) / dynamicPeak;

        if (currentStaticDD > staticMaxDD) staticMaxDD = currentStaticDD;
        if (currentDynamicDD > dynamicMaxDD) dynamicMaxDD = currentDynamicDD;

        chartData.push({
          date: dates[i],
          price: Number(prices[i].toFixed(2)),
          regime: regimes[i],
          staticEquity: Math.round(staticCapital),
          dynamicEquity: Math.round(dynamicCapital)
        });
      }

      const mean = arr => arr.reduce((a, b) => a + b, 0) / arr.length;
      const std = (arr, m) => Math.sqrt(arr.reduce((a, b) => a + Math.pow(b - m, 2), 0) / arr.length);

      const meanStatic = mean(staticReturnsList);
      const meanDynamic = mean(dynamicReturnsList);
      
      const stdStatic = std(staticReturnsList, meanStatic);
      const stdDynamic = std(dynamicReturnsList, meanDynamic);

      const staticSharpe = stdStatic === 0 ? 0 : (meanStatic / stdStatic) * Math.sqrt(252);
      const dynamicSharpe = stdDynamic === 0 ? 0 : (meanDynamic / stdDynamic) * Math.sqrt(252);

      res.json({
        currentRegime: regimes[regimes.length - 1],
        metrics: {
          staticReturn: (((staticCapital - 100000) / 100000) * 100).toFixed(2),
          dynamicReturn: (((dynamicCapital - 100000) / 100000) * 100).toFixed(2),
          staticMaxDD: (staticMaxDD * 100).toFixed(2),
          dynamicMaxDD: (dynamicMaxDD * 100).toFixed(2),
          staticSharpe: staticSharpe.toFixed(2),
          dynamicSharpe: dynamicSharpe.toFixed(2)
        },
        chartData
      });

    } catch (parseError) {
      res.status(500).json({ error: "Failed to parse Python bridge JSON output." });
    }
  });
});

app.listen(PORT, () => console.log(`Backend running on http://localhost:${PORT}`));
