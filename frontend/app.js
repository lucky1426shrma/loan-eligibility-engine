// The Loan Eligibility Engine - Frontend Console Controller
// Implements direct-to-S3 presigned upload & live pipeline tracking

const API_BASE_URL = window.location.origin.includes('5173') 
  ? 'http://localhost:8000' 
  : window.location.origin;

// DOM Elements
const dropzone = document.getElementById('dropzone');
const fileInput = document.getElementById('file-input');
const browseBtn = document.getElementById('browse-btn');
const filePreviewBar = document.getElementById('file-preview-bar');
const selectedFileName = document.getElementById('selected-file-name');
const selectedFileSize = document.getElementById('selected-file-size');
const removeFileBtn = document.getElementById('remove-file-btn');
const startUploadBtn = document.getElementById('start-upload-btn');
const pipelineTracker = document.getElementById('pipeline-tracker');
const progressBarFill = document.getElementById('progress-bar-fill');
const progressStatusLabel = document.getElementById('progress-status-label');
const resultsBox = document.getElementById('results-box');
const downloadSampleBtn = document.getElementById('download-sample-csv');

// Metric Elements
const statProducts = document.getElementById('stat-products');
const statUsers = document.getElementById('stat-users');
const statMatches = document.getElementById('stat-matches');
const statArchetypes = document.getElementById('stat-archetypes');

// Step Elements
const stepS3 = document.getElementById('step-s3');
const stepLambda = document.getElementById('step-lambda');
const stepMatching = document.getElementById('step-matching');
const stepNotify = document.getElementById('step-notify');

let currentFile = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  fetchDashboardStats();
  setupEventListeners();
});

function setupEventListeners() {
  browseBtn.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', handleFileSelected);

  // Drag & drop
  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('dragover');
  });

  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));

  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    if (e.dataTransfer.files.length > 0) {
      setFile(e.dataTransfer.files[0]);
    }
  });

  removeFileBtn.addEventListener('click', resetFileSelection);
  startUploadBtn.addEventListener('click', startPipeline);
  downloadSampleBtn.addEventListener('click', downloadSampleCsv);
}

function handleFileSelected(e) {
  if (e.target.files.length > 0) {
    setFile(e.target.files[0]);
  }
}

function setFile(file) {
  if (!file.name.toLowerCase().endsWith('.csv')) {
    alert('Please select a valid .csv file.');
    return;
  }
  currentFile = file;
  selectedFileName.textContent = file.name;
  selectedFileSize.textContent = formatBytes(file.size);
  dropzone.style.display = 'none';
  filePreviewBar.style.display = 'flex';
  resultsBox.style.display = 'none';
  pipelineTracker.style.display = 'none';
}

function resetFileSelection() {
  currentFile = null;
  fileInput.value = '';
  filePreviewBar.style.display = 'none';
  dropzone.style.display = 'block';
  pipelineTracker.style.display = 'none';
}

function formatBytes(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

async function fetchDashboardStats() {
  try {
    const res = await fetch(`${API_BASE_URL}/api/stats`);
    if (res.ok) {
      const data = await res.json();
      statProducts.textContent = data.active_loan_products ?? '--';
      statUsers.textContent = (data.total_users ?? 0).toLocaleString();
      statMatches.textContent = (data.total_matches_generated ?? 0).toLocaleString();
      statArchetypes.textContent = data.cached_archetypes ?? '--';
    }
  } catch (err) {
    console.warn('Could not fetch metrics:', err);
  }
}

// Direct-to-S3 Presigned Upload Pipeline
async function startPipeline() {
  if (!currentFile) return;

  startUploadBtn.disabled = true;
  pipelineTracker.style.display = 'block';
  resultsBox.style.display = 'none';
  
  setStepState('step-s3', 'active');
  setProgress(15, 'Requesting S3 Presigned Upload URL...');

  try {
    // 1. Request S3 Presigned URL from Lambda / API Gateway
    const presignRes = await fetch(`${API_BASE_URL}/upload-url?filename=${encodeURIComponent(currentFile.name)}`);
    if (!presignRes.ok) {
      throw new Error(`Failed to obtain presigned URL: ${presignRes.statusText}`);
    }
    const { upload_url, job_id, s3_key } = await presignRes.json();

    // 2. Direct HTTP PUT upload to S3
    setProgress(35, 'Uploading CSV directly to Amazon S3...');
    await uploadDirectToS3(upload_url, currentFile);

    setStepState('step-s3', 'completed');
    setStepState('step-lambda', 'active');
    setProgress(60, 'S3 Event triggered: Streaming CSV parse and PostgreSQL COPY...');

    // 3. Poll job status & n8n matching
    pollJobStatus(job_id);

  } catch (err) {
    console.error('Pipeline error:', err);
    setProgress(100, `Pipeline failed: ${err.message}`);
    startUploadBtn.disabled = false;
  }
}

function uploadDirectToS3(url, file) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('PUT', url, true);
    xhr.setRequestHeader('Content-Type', 'text/csv');

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        const pct = Math.round((e.loaded / e.total) * 40) + 15; // 15% to 55%
        setProgress(pct, `Uploading directly to Amazon S3 (${Math.round((e.loaded/e.total)*100)}%)...`);
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve();
      } else {
        reject(new Error(`S3 upload returned HTTP ${xhr.status}: ${xhr.statusText}`));
      }
    };

    xhr.onerror = () => reject(new Error('Network error during S3 direct upload.'));
    xhr.send(file);
  });
}

async function pollJobStatus(jobId) {
  let attempts = 0;
  const maxAttempts = 30;

  const interval = setInterval(async () => {
    attempts++;
    try {
      const res = await fetch(`${API_BASE_URL}/api/jobs/${jobId}`);
      if (res.ok) {
        const data = await res.json();
        const job = data.job;

        if (job.status === 'COMPLETED') {
          clearInterval(interval);
          setStepState('step-lambda', 'completed');
          setStepState('step-matching', 'completed');
          setStepState('step-notify', 'completed');
          setProgress(100, 'All workflows finished successfully!');

          // Show Results Box
          document.getElementById('res-job-id').textContent = jobId;
          document.getElementById('res-valid-rows').textContent = `${job.valid_rows} rows`;
          document.getElementById('res-quarantined').textContent = `${job.quarantined_rows} rows`;
          document.getElementById('res-matches').textContent = `${data.matches_found} offers generated`;
          document.getElementById('res-notification').textContent = `${data.notified_count || data.matches_found} alerts delivered to test alias`;
          resultsBox.style.display = 'block';

          startUploadBtn.disabled = false;
          fetchDashboardStats();
          return;
        } else if (job.status === 'FAILED') {
          clearInterval(interval);
          setProgress(100, `Ingestion failed: ${job.error_message}`);
          startUploadBtn.disabled = false;
          return;
        }
      }
    } catch (err) {
      console.warn('Poll error:', err);
    }

    if (attempts >= maxAttempts) {
      clearInterval(interval);
      setProgress(100, 'Ingestion submitted. Processing asynchronously in background.');
      startUploadBtn.disabled = false;
    }
  }, 1000);
}

function setStepState(stepId, state) {
  const el = document.getElementById(stepId);
  if (!el) return;
  el.classList.remove('active', 'completed');
  if (state) el.classList.add(state);
}

function setProgress(percent, label) {
  progressBarFill.style.width = `${percent}%`;
  progressStatusLabel.textContent = label;
}

// Sample CSV Generator (Conforming to assignment requirements)
function downloadSampleCsv() {
  const headers = 'user_id,email,monthly_income,credit_score,employment_status,age\n';
  const rows = [
    'USR-1001,applicant.one@gmail.com,85000,780,employed,29',
    'USR-1002,applicant.two@gmail.com,45000,710,employed,34',
    'USR-1003,applicant.three@gmail.com,32000,670,employed,24',
    'USR-1004,applicant.four@gmail.com,120000,810,self_employed,42',
    'USR-1005,applicant.five@gmail.com,26000,655,employed,22',
    'USR-1006,applicant.six@gmail.com,58000,735,self_employed,38',
    'USR-1007,applicant.seven@gmail.com,18000,590,employed,20', // subprime test (should filter out)
    'USR-1008,applicant.eight@gmail.com,95000,765,employed,31'
  ].join('\n');

  const blob = new Blob([headers + rows], { type: 'text/csv' });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.setAttribute('href', url);
  a.setAttribute('download', 'users.csv');
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}
