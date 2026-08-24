/* =========================================================================
     CONNECTING THIS TO YOUR REAL SYSTEM
     -------------------------------------------------------------------------
    This page starts with fixed sample data so it remains useful when the
    backend is offline. When the API is available, loadLatestReading() below
    replaces the sample with the latest stored sensor reading.

     Example shape your backend should return as JSON:
     {
       "contaminant": "Arsenic (As)",
       "value": 0.018,
       "unit": "mg/L",
       "safeLimit": 0.010,
       "confidencePct": 94,
       "confirmedByHomes": 3,
       "source": "Groundwater",
       "detectedAt": "07:42",
       "batteryPct": 71,
       "lastPatrolMin": 12,
       "nextPatrolMin": 48
     }

     Example polling loop (uncomment and point at your API):

     async function pollReading() {
       const res = await fetch("https://your-backend.example.com/api/latest-reading");
       const data = await res.json();
       renderReading(data);
     }
     setInterval(pollReading, 60000); // check every 60 seconds
     pollReading();
  ========================================================================= */

  const API_BASE_URL = window.AQUASENTRY_API_URL || "http://localhost:8000";
  const DEVICE_CODE = "AQUA-001";
  const POLL_INTERVAL_MS = 30000;
  const analytes = {
    As: { label: "Arsenic (III) · strip As-M003050", unit: "mg/L", peakV: -800, searchWindow: 60, shoulder: 40, calSlope: 0.8563, calIntercept: 0.0096, calR2: 0.9967, lod: 0.02, quantRange: [0.03, 0.50], implemented: true, digits: 3 },
  };
  const analyteOrder = ["As"];
  let currentAnalyte = "As";
  let scanRunning = false;
  const scanHistory = JSON.parse(localStorage.getItem("aquaSentryMasG1History") || "{}");

  function formatDetectedAt(value) {
    if (!value) return "UNKNOWN TIME";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString([], { hour: "2-digit", minute: "2-digit", hour12: false });
  }

  function renderReading(data) {
    const contaminantName = data.contaminant || "Unknown contaminant";
    const value = Number(data.value);
    const safeLimit = Number(data.safeLimit);
    const classification = String(data.classification || "").toLowerCase();
    const statusTone = classification === "safe" || (!classification && value <= safeLimit)
      ? "safe"
      : classification === "caution" || classification === "intermediate" || (!classification && value <= safeLimit * 5)
        ? "intermediate"
        : "danger";
    const isUnsafe = statusTone === "danger";
    const readingState = statusTone === "safe"
      ? "Water within safe limit"
      : statusTone === "intermediate"
        ? "Water needs caution"
        : "Contamination detected";
    document.querySelector('.hero').className = `hero status-${statusTone}`;
    document.querySelector('.core-value').textContent = data.value ?? "—";
    document.querySelector('.core-unit').textContent = data.unit || "";
    document.querySelector('.core-label').textContent = contaminantName.split(' ')[0].toUpperCase();
    const statusTitle = document.querySelector('.status-title');
    statusTitle.replaceChildren(document.createTextNode(`${readingState.split(' ')[0]} `));
    const statusHighlight = document.createElement('span');
    statusHighlight.className = 'hl';
    statusHighlight.textContent = readingState.split(' ').slice(1).join(' ');
    statusTitle.append(statusHighlight);
    document.querySelector('.status-sub').textContent = statusTone === "danger"
      ? `${contaminantName} is at a dangerous level. Do not drink or cook with this water until a follow-up reading confirms it is safe.`
      : statusTone === "intermediate"
        ? `${contaminantName} is above the healthy limit but below the dangerous range. Use caution and arrange a follow-up test.`
        : `${contaminantName} is currently within the healthy drinking threshold. Continue regular monitoring.`;

    const cells = document.querySelectorAll('.reading-cell .v');
    cells[0].textContent = `${data.value ?? "—"} ${data.unit || ""}`.trim();
    cells[0].classList.toggle("danger", isUnsafe);
    cells[0].classList.toggle("warning", statusTone === "intermediate");
    cells[1].textContent = `${data.confidencePct ?? "—"}%`;
    cells[2].textContent = data.source || "Unknown";
    document.querySelector('#contaminantName').textContent = contaminantName;
    document.querySelector('#detectedMeta').textContent = `DETECTED ${formatDetectedAt(data.detectedAt)} · ${data.recordedLabel || "LATEST"}`;
    document.querySelector('#sourceNote').textContent = data.sourceNote || "Source estimate from latest reading";
    document.querySelector('#reportBox').textContent = [
      `STATION       ${data.deviceCode || DEVICE_CODE}`,
      `CONTAMINANT   ${contaminantName}`,
      `READING       ${data.value ?? "—"} ${data.unit || ""}`.trim(),
      `(LIMIT        ${data.safeLimit ?? "—"} ${data.unit || ""})`.trim(),
      `DETECTED      ${formatDetectedAt(data.detectedAt)}`,
      `STATUS        ${isUnsafe ? "Action required" : "Monitoring"}`,
    ].join("\n");

    document.querySelectorAll('.reading-cell .thresh')[0].textContent = `safe limit: ${data.safeLimit ?? "—"} ${data.unit || ""}`.trim();
    document.querySelectorAll('.reading-cell .thresh')[1].textContent = `verified across ${data.confirmedByHomes ?? 0} nearby homes`;

    document.querySelector('footer span:first-child').textContent =
      `MINIBOT · BATTERY ${data.batteryPct ?? "—"}% · LAST PATROL ${data.lastPatrolMin ?? "—"} MIN AGO`;
    document.querySelector('footer span:last-child').textContent =
      `NEXT PATROL IN ${data.nextPatrolMin ?? "—"} MIN`;
  }

  async function loadLatestReading() {
    const connectionStatus = document.querySelector('#connectionStatus');
    try {
      const response = await fetch(`${API_BASE_URL}/api/dashboard/latest?device_code=${encodeURIComponent(DEVICE_CODE)}`, { cache: "no-store" });
      if (!response.ok) throw new Error(`API returned ${response.status}`);
      const reading = await response.json();
      renderReading({ ...reading, deviceCode: DEVICE_CODE });
      connectionStatus.classList.add("connected");
      connectionStatus.lastChild.textContent = " MINIBOT CONNECTED";
    } catch (error) {
      connectionStatus.classList.remove("connected");
      connectionStatus.lastChild.textContent = " DEMO DATA · API OFFLINE";
      console.info("AquaSentry API unavailable; showing demo data.", error);
    }
  }

  const simulator = {
    value: document.querySelector('#simulatorValue'), unit: document.querySelector('#simulatorUnit'), analyte: document.querySelector('#simulatorAnalyte'),
    flag: document.querySelector('#simulatorFlag'), flagText: document.querySelector('#simulatorFlagText'), state: document.querySelector('#simulatorScanState'),
    trace: document.querySelector('#simulatorTraceSvg'), peakV: document.querySelector('#simulatorPeakV'), netI: document.querySelector('#simulatorNetI'), r2: document.querySelector('#simulatorR2'),
    note: document.querySelector('#simulatorNote'), historyCount: document.querySelector('#simulatorHistoryCount'), historyList: document.querySelector('#simulatorHistoryList'),
  };

  function gaussianNoise(sigma) { let u = 0; let v = 0; while (!u) u = Math.random(); while (!v) v = Math.random(); return sigma * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }
  function generateVoltammogram(concentration, cfg) {
    const pot = []; const cur = [];
    for (let voltage = -1000; voltage <= -600; voltage += 5) { pot.push(voltage); cur.push(0.05 + 0.00015 * (voltage + 1000) + 0.9 * concentration * Math.exp(-0.5 * ((voltage - cfg.peakV) / 15) ** 2) + gaussianNoise(0.02)); }
    return { pot, cur };
  }
  function smooth(cur) { return cur.map((value, index) => index < 2 || index > cur.length - 3 ? value : cur.slice(index - 2, index + 3).reduce((sum, item) => sum + item, 0) / 5); }
  function fitBaseline(pot, cur, cfg) {
    const low = cfg.peakV - cfg.searchWindow; const high = cfg.peakV + cfg.searchWindow; const xs = []; const ys = [];
    pot.forEach((voltage, index) => { if ((voltage >= low - cfg.shoulder && voltage < low) || (voltage > high && voltage <= high + cfg.shoulder)) { xs.push(voltage); ys.push(cur[index]); } });
    if (xs.length < 2) return pot.map(() => Math.min(...cur));
    const n = xs.length; const sx = xs.reduce((sum, value) => sum + value, 0); const sy = ys.reduce((sum, value) => sum + value, 0); const sxx = xs.reduce((sum, value) => sum + value * value, 0); const sxy = xs.reduce((sum, value, index) => sum + value * ys[index], 0);
    const slope = (n * sxy - sx * sy) / (n * sxx - sx * sx); const intercept = (sy - slope * sx) / n;
    return pot.map((voltage) => slope * voltage + intercept);
  }
  function findPeak(pot, cur, baseline, cfg) {
    const low = cfg.peakV - cfg.searchWindow; const high = cfg.peakV + cfg.searchWindow; let index = -1; let net = -Infinity;
    pot.forEach((voltage, item) => { const candidate = cur[item] - baseline[item]; if (voltage >= low && voltage <= high && candidate > net) { index = item; net = candidate; } });
    return { peakV: pot[index], rawI: cur[index], netI: net };
  }
  function drawTrace(pot, cur, baseline, peak, reveal) {
    const width = 520; const height = 120; const x = (value) => 6 + (value - Math.min(...pot)) / (Math.max(...pot) - Math.min(...pot)) * 508; const min = Math.min(...cur); const range = Math.max(...cur) - min || 1; const y = (value) => 110 - (value - min) / range * 100; const shown = Math.max(2, Math.floor(pot.length * reveal));
    const path = (values) => values.slice(0, shown).map((value, index) => `${index ? 'L' : 'M'}${x(pot[index])} ${y(value)}`).join(' ');
    let svg = ''; for (let index = 0; index <= 4; index += 1) svg += `<line x1="${6 + index * 127}" y1="10" x2="${6 + index * 127}" y2="110" stroke="#123c35"/>`; for (let index = 0; index <= 3; index += 1) svg += `<line x1="6" y1="${10 + index * 33.3}" x2="514" y2="${10 + index * 33.3}" stroke="#123c35"/>`;
    svg += `<path d="${path(baseline)}" fill="none" stroke="#2b8f73" stroke-dasharray="3,3"/><path d="${path(cur)}" fill="none" stroke="#45e0b0" stroke-width="2"/>`;
    if (reveal >= 1 && peak) svg += `<circle cx="${x(peak.peakV)}" cy="${y(peak.rawI)}" r="4" fill="#45e0b0"/>`;
    simulator.trace.innerHTML = svg;
  }
  function setSimulatorFlag(kind, text) { simulator.flag.className = `simulator-flag ${kind}`; simulator.flagText.textContent = text; }
  function renderSimulatorHistory() { const list = scanHistory[currentAnalyte] || []; simulator.historyCount.textContent = list.length; simulator.historyList.innerHTML = list.length ? list.slice(-4).reverse().map((item) => `<div class="simulator-history-row ${item.kind}"><span>${item.time}</span><strong>${item.conc.toFixed(3)} ${item.unit}</strong></div>`).join('') : '<div class="simulator-history-row"><span>no runs yet</span><span>--</span></div>'; }
  function selectAnalyte(key) { if (scanRunning) return; currentAnalyte = key; const cfg = analytes[key]; document.querySelectorAll('.simulator-tab').forEach((tab) => tab.classList.toggle('active', tab.dataset.analyte === key)); simulator.analyte.textContent = cfg.label.toUpperCase(); simulator.unit.textContent = cfg.unit; simulator.value.textContent = '--.---'; simulator.peakV.textContent = '--'; simulator.netI.textContent = '--'; simulator.r2.textContent = cfg.calR2?.toFixed(4) || '--'; simulator.trace.innerHTML = ''; simulator.state.textContent = 'IDLE'; setSimulatorFlag('idle', cfg.implemented ? 'READY · IMPORT OR RUN DEMO' : `INSERT ${key}-M CHIP TO CALIBRATE`); simulator.note.textContent = ''; renderSimulatorHistory(); }
  function classify(concentration, cfg) { if (concentration < cfg.lod) return { kind: 'idle', text: `BELOW LOD (${cfg.lod} ${cfg.unit}) · NOT DETECTED` }; if (concentration < cfg.quantRange[0]) return { kind: 'warn', text: 'BELOW QUANT RANGE · ESTIMATE ONLY' }; if (concentration > cfg.quantRange[1]) return { kind: 'danger', text: 'ABOVE RANGE · DILUTE & RE-RUN' }; return { kind: 'ok', text: 'WITHIN VALIDATED RANGE' }; }
  function finishScan(data, label) { const cfg = analytes[currentAnalyte]; const current = smooth(data.cur); const baseline = fitBaseline(data.pot, current, cfg); let frame = 0; simulator.state.textContent = 'PROCESSING'; scanRunning = true; const timer = setInterval(() => { frame += 1; drawTrace(data.pot, current, baseline, null, frame / 25); if (frame >= 25) { clearInterval(timer); const peak = findPeak(data.pot, current, baseline, cfg); const concentration = Math.max(0, (peak.netI - cfg.calIntercept) / cfg.calSlope); const status = classify(concentration, cfg); drawTrace(data.pot, current, baseline, peak, 1); simulator.value.textContent = concentration.toFixed(cfg.digits); simulator.peakV.textContent = `${peak.peakV} mV`; simulator.netI.textContent = peak.netI.toFixed(4); simulator.state.textContent = 'COMPLETE'; setSimulatorFlag(status.kind, status.text); simulator.note.textContent = 'Dashboard preview updated. This scan did not write to the backend database.'; renderReading({ contaminant: 'Arsenic (As)', value: concentration.toFixed(4), unit: cfg.unit, safeLimit: '0.0100', confidencePct: 96, confirmedByHomes: 0, source: 'MAS-G1 simulation', sourceNote: 'Simulated device reading, not stored in backend', detectedAt: new Date().toISOString(), deviceCode: DEVICE_CODE, batteryPct: 71, lastPatrolMin: 0 }); const entry = { time: label || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }), conc: concentration, unit: cfg.unit, kind: status.kind }; scanHistory[currentAnalyte] = [...(scanHistory[currentAnalyte] || []), entry].slice(-100); localStorage.setItem('aquaSentryMasG1History', JSON.stringify(scanHistory)); renderSimulatorHistory(); scanRunning = false; } }, 40); }
  function runSimulation() { const cfg = analytes[currentAnalyte]; if (scanRunning) return; if (!cfg.implemented) { setSimulatorFlag('warn', `NO CALIBRATION FOR ${currentAnalyte}`); return; } simulator.note.textContent = 'Generating synthetic voltammogram…'; setSimulatorFlag('idle', 'PROCESSING SCAN DATA…'); finishScan(generateVoltammogram(0.01 + Math.random() * 0.55, cfg), 'demo'); }
  function parseCSV(text) { const lines = text.split(/\r?\n/).filter((line) => line.trim()); if (lines.length < 2) throw new Error('CSV has no data rows'); const header = lines[0].split(',').map((value) => value.trim().toLowerCase()); const voltageIndex = header.indexOf('potential_mv'); const currentIndex = header.indexOf('current_ua'); if (voltageIndex < 0 || currentIndex < 0) throw new Error('expected columns potential_mV,current_uA'); const rows = lines.slice(1).map((line) => line.split(',')).map((columns) => [Number.parseFloat(columns[voltageIndex]), Number.parseFloat(columns[currentIndex])]).filter(([voltage, current]) => Number.isFinite(voltage) && Number.isFinite(current)).sort((a, b) => a[0] - b[0]); if (rows.length < 5) throw new Error('not enough valid rows'); return { pot: rows.map((row) => row[0]), cur: rows.map((row) => row[1]) }; }
  function importScans(files) { const cfg = analytes[currentAnalyte]; if (!cfg.implemented) return setSimulatorFlag('warn', `NO CALIBRATION FOR ${currentAnalyte}`); [...files].forEach((file) => { const reader = new FileReader(); reader.onload = () => { try { finishScan(parseCSV(reader.result), file.name.replace(/\.csv$/i, '').slice(0, 16)); } catch (error) { simulator.note.textContent = `${file.name}: ${error.message}`; } }; reader.readAsText(file); }); }
  function importCalibration(file) { const reader = new FileReader(); reader.onload = () => { try { const calibration = JSON.parse(reader.result); const cfg = analytes[currentAnalyte]; if (typeof calibration.slope !== 'number' || typeof calibration.intercept !== 'number') throw new Error('missing slope/intercept'); cfg.calSlope = calibration.slope; cfg.calIntercept = calibration.intercept; cfg.calR2 = typeof calibration.r_squared === 'number' ? calibration.r_squared : cfg.calR2; cfg.implemented = true; selectAnalyte(currentAnalyte); simulator.note.textContent = `Calibration loaded for ${currentAnalyte} · R² ${cfg.calR2?.toFixed(4) || '?'}`; } catch (error) { simulator.note.textContent = `Bad calibration.json: ${error.message}`; } }; reader.readAsText(file); }
  function exportHistory() { const rows = ['time,analyte,concentration_mgL,status']; (scanHistory[currentAnalyte] || []).forEach((item) => rows.push([item.time, currentAnalyte, item.conc.toFixed(4), item.kind].join(','))); const link = document.createElement('a'); link.href = URL.createObjectURL(new Blob([rows.join('\n')], { type: 'text/csv' })); link.download = `mas-g1_${currentAnalyte}_history.csv`; link.click(); URL.revokeObjectURL(link.href); }

  document.querySelectorAll('.simulator-tab').forEach((tab) => tab.addEventListener('click', () => selectAnalyte(tab.dataset.analyte)));
  document.querySelector('#runSimulation').addEventListener('click', runSimulation);
  document.querySelector('#importScan').addEventListener('click', () => document.querySelector('#scanFileInput').click());
  document.querySelector('#scanFileInput').addEventListener('change', (event) => importScans(event.target.files));
  document.querySelector('#importCalibration').addEventListener('click', () => document.querySelector('#calibrationFileInput').click());
  document.querySelector('#calibrationFileInput').addEventListener('change', (event) => { if (event.target.files[0]) importCalibration(event.target.files[0]); });
  document.querySelector('#exportHistory').addEventListener('click', exportHistory);
  selectAnalyte('As');


  // Simple browser notification, for when a real reading crosses a danger threshold.
  // Call requestNotifyPermission() once (e.g. on a settings toggle), then
  // call notifyUser() whenever a new dangerous reading comes in from your backend.
  function requestNotifyPermission() {
    if ("Notification" in window) Notification.requestPermission();
  }
  function notifyUser(title, body) {
    if ("Notification" in window && Notification.permission === "granted") {
      new Notification(title, { body });
    }
  }

  loadLatestReading();
  setInterval(loadLatestReading, POLL_INTERVAL_MS);
