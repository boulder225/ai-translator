import axios from 'axios';

const API_BASE_URL = '/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const listGlossaries = async () => {
  const response = await api.get('/glossaries');
  return response.data;
};

export const getPrompt = async () => {
  const response = await api.get('/prompt');
  return response.data;
};

export const startTranslation = async (file, options) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('source_lang', options.source_lang || 'fr');
  formData.append('target_lang', options.target_lang || 'it');
  formData.append('use_glossary', options.use_glossary !== false);
  formData.append('skip_memory', options.skip_memory !== false);
  
  if (options.custom_prompt) {
    formData.append('custom_prompt', options.custom_prompt);
  }

  const response = await axios.post(`${API_BASE_URL}/translate`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  
  return response.data;
};

export const getTranslationStatus = async (jobId) => {
  const response = await api.get(`/translate/${jobId}/status`);
  return response.data;
};

export const downloadTranslation = async (jobId) => {
  // #region agent log
  fetch('http://127.0.0.1:7242/ingest/c9cfb42e-68cf-4957-89f2-8cb5ca71e323',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'api.js:48',message:'downloadTranslation called',data:{jobId,typeofJobId:typeof jobId},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A,B'})}).catch(()=>{});
  // #endregion
  
  const url = `/translate/${jobId}/download`;
  // #region agent log
  fetch('http://127.0.0.1:7242/ingest/c9cfb42e-68cf-4957-89f2-8cb5ca71e323',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'api.js:52',message:'Request URL before call',data:{url,usingApiInstance:true,baseURL:API_BASE_URL,fullUrl:`${API_BASE_URL}${url}`,jobId},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A,B'})}).catch(()=>{});
  // #endregion
  
  try {
    // Use api instance instead of axios directly to get /api prefix automatically
    const response = await api.get(url, {
      responseType: 'blob',
    });
    
    // #region agent log
    const blobSize = response.data instanceof Blob ? response.data.size : null;
    const firstBytes = response.data instanceof Blob ? 'Blob' : String(response.data).substring(0, 50);
    fetch('http://127.0.0.1:7242/ingest/c9cfb42e-68cf-4957-89f2-8cb5ca71e323',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'api.js:60',message:'Response received',data:{jobId,status:response.status,statusText:response.statusText,contentType:response.headers['content-type'],dataType:typeof response.data,dataSize:blobSize,isBlob:response.data instanceof Blob,firstBytes},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C,D,E'})}).catch(()=>{});
    // #endregion
    
    // Check if response is HTML (error page)
    if (response.headers['content-type']?.includes('text/html')) {
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/c9cfb42e-68cf-4957-89f2-8cb5ca71e323',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'api.js:65',message:'HTML response detected',data:{contentType:response.headers['content-type']},timestamp:Date.now(),sessionId:'debug-session',runId:'post-fix',hypothesisId:'C'})}).catch(()=>{});
      // #endregion
      const text = await response.data.text();
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/c9cfb42e-68cf-4957-89f2-8cb5ca71e323',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'api.js:68',message:'HTML content preview',data:{preview:text.substring(0,200)},timestamp:Date.now(),sessionId:'debug-session',runId:'post-fix',hypothesisId:'C'})}).catch(()=>{});
      // #endregion
      throw new Error('Server returned HTML instead of PDF. Check URL and endpoint.');
    }
    
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/c9cfb42e-68cf-4957-89f2-8cb5ca71e323',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'api.js:72',message:'Creating blob',data:{blobType:'application/pdf'},timestamp:Date.now(),sessionId:'debug-session',runId:'post-fix',hypothesisId:'D,E'})}).catch(()=>{});
    // #endregion
    
    // Create download link
    const url_blob = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }));
    const link = document.createElement('a');
    link.href = url_blob;
    link.setAttribute('download', `translated_${jobId}.pdf`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url_blob);
    
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/c9cfb42e-68cf-4957-89f2-8cb5ca71e323',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'api.js:82',message:'Download link clicked',data:{success:true},timestamp:Date.now(),sessionId:'debug-session',runId:'post-fix',hypothesisId:'D,E'})}).catch(()=>{});
    // #endregion
  } catch (error) {
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/c9cfb42e-68cf-4957-89f2-8cb5ca71e323',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'api.js:85',message:'Download error',data:{error:error.message,status:error.response?.status,statusText:error.response?.statusText,responseType:error.response?.data?.constructor?.name},timestamp:Date.now(),sessionId:'debug-session',runId:'post-fix',hypothesisId:'A,B,C'})}).catch(()=>{});
    // #endregion
    throw error;
  }
};

export const cancelTranslation = async (jobId) => {
  const response = await api.post(`/translate/${jobId}/cancel`);
  return response.data;
};

export const getTranslationReport = async (jobId) => {
  const response = await api.get(`/translate/${jobId}/report`);
  return response.data;
};

export const downloadTranslatedText = async (jobId) => {
  // Use api instance for consistency
  const response = await api.get(`/translate/${jobId}/text`, {
    responseType: 'blob',
  });
  
  // Create download link
  const url = window.URL.createObjectURL(new Blob([response.data], { type: 'text/plain' }));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `translated_${jobId}.txt`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

