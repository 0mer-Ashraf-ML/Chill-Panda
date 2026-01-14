let chat_socket;
let language = "en";
let role = "loyal_best_friend";
let audioQueue = [];
let isPlaying = false;
let refreshMsgText = false;
const chatContainer = document.getElementById('chat_container');
const inputField = document.getElementById("user-text-msg");
const userMsgDiv = document.getElementById('user-msg');
const llmResponseDiv = document.getElementById('llm-msg');
const sendBtn = document.getElementById("user-text-msg");
let audioContext = new (window.AudioContext || window.webkitAudioContext)();

// Track currently playing audio source for interruption
let currentAudioSource = null;

// Voice usage tracking state
let voiceEnabled = true;
let voiceLimitReached = null;

// UUID Management
function generateUUID() {
  if (crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

// Session ID (UUID) Management
function getStoredUUID() {
  return localStorage.getItem('voice_engine_uuid');
}

function setStoredUUID(uuid) {
  localStorage.setItem('voice_engine_uuid', uuid);
  const uuidField = document.getElementById('uuid-field');
  if (uuidField) uuidField.value = uuid;
}

function initUUID() {
  const uuidField = document.getElementById('uuid-field');
  const generateBtn = document.getElementById('generate-uuid-btn');

  let currentUUID = getStoredUUID();
  if (!currentUUID) {
    currentUUID = generateUUID();
    setStoredUUID(currentUUID);
  }

  if (uuidField) {
    uuidField.value = currentUUID;
    uuidField.removeAttribute('readonly');
    uuidField.addEventListener('change', (e) => {
      const val = e.target.value.trim();
      if (val && val.length === 36) {
        setStoredUUID(val);
      }
    });
  }

  if (generateBtn) {
    generateBtn.addEventListener('click', () => {
      if (confirm("Generate new Session ID? This will start a fresh conversation.")) {
        const newUUID = generateUUID();
        setStoredUUID(newUUID);
        window.location.reload();
      }
    });
  }

  return currentUUID;
}

// User ID Management (for voice usage tracking)
function getStoredUserID() {
  return localStorage.getItem('voice_engine_user_id');
}

function setStoredUserID(userId) {
  localStorage.setItem('voice_engine_user_id', userId);
  const userIdField = document.getElementById('user-id-field');
  if (userIdField) userIdField.value = userId;
}

function initUserID() {
  const userIdField = document.getElementById('user-id-field');
  const generateUserIdBtn = document.getElementById('generate-user-id-btn');

  // Load existing User ID or generate new one
  let currentUserID = getStoredUserID();
  if (!currentUserID) {
    currentUserID = generateUUID();
    setStoredUserID(currentUserID);
  }

  if (userIdField) {
    userIdField.value = currentUserID;
    userIdField.removeAttribute('readonly');
    userIdField.addEventListener('change', (e) => {
      const val = e.target.value.trim();
      if (val && val.length > 0) {
        setStoredUserID(val);
      }
    });
  }

  if (generateUserIdBtn) {
    generateUserIdBtn.addEventListener('click', () => {
      if (confirm("Generate new User ID? This will reset your voice usage tracking.")) {
        const newUserID = generateUUID();
        setStoredUserID(newUserID);
        window.location.reload();
      }
    });
  }

  return currentUserID;
}

// Handle voice limit notifications
function handleVoiceLimitReached(data) {
  voiceEnabled = false;
  voiceLimitReached = data.limit_type;

  console.log(`[VOICE_LIMIT] ${data.limit_type} limit reached: ${data.message}`);

  // Show notification to user
  const notification = document.getElementById('voice-limit-notification');
  if (notification) {
    notification.textContent = data.message;
    notification.style.display = 'block';
  } else {
    alert(data.message);
  }

  // Update UI to show voice is disabled
  const voiceStatusEl = document.getElementById('voice-status');
  if (voiceStatusEl) {
    voiceStatusEl.textContent = 'Voice Disabled';
    voiceStatusEl.classList.add('disabled');
  }
}

function handleVoiceWarning(data) {
  console.log(`[VOICE_WARNING] ${data.limit_type}: ${data.remaining_minutes.toFixed(1)} minutes remaining`);

  // Show warning to user
  const warningEl = document.getElementById('voice-warning');
  if (warningEl) {
    warningEl.textContent = data.message;
    warningEl.style.display = 'block';
    // Auto-hide after 10 seconds
    setTimeout(() => {
      warningEl.style.display = 'none';
    }, 10000);
  }
}

async function getMicrophone() {
  const userMedia = await navigator.mediaDevices.getUserMedia({
    audio: true,
  });

  return new MediaRecorder(userMedia);
}

async function openMicrophone(microphone, socket) {
  await microphone.start(500);

  microphone.onstart = () => {
    console.log("client: microphone opened");
  };

  microphone.onstop = () => {
    console.log("client: microphone closed");
  };

  microphone.ondataavailable = (e) => {
    socket.send(e.data);
    console.log(`Data-Sent : ${socket}`)
  };
}

async function closeMicrophone(microphone) {
  microphone.stop();
}

async function start(socket) {
  const listenButton = document.getElementById("record");
  let microphone;

  console.log("client: waiting to open microphone");

  listenButton.addEventListener("click", async () => {
    if (!microphone) {
      microphone = await getMicrophone();
      await openMicrophone(microphone, socket);
    } else {
      await closeMicrophone(microphone);
      userMsgDiv.innerHTML = ""
      llmResponseDiv.innerHTML = ""

      stopAudio();
      microphone = undefined;
    }
  });
}

// Stop all audio including currently playing
function stopAudio() {
  // Stop currently playing audio source
  if (currentAudioSource) {
    try {
      currentAudioSource.stop();
      currentAudioSource.disconnect();
    } catch (e) {
      // Ignore errors if already stopped
    }
    currentAudioSource = null;
  }

  // Clear the audio queue
  audioQueue = [];
  isPlaying = false;
  console.log("Audio stopped and queue cleared");
}

function playNextAudio() {
  if (audioQueue.length > 0 && !isPlaying) {
    isPlaying = true;
    const data = audioQueue.shift();
    console.log(`Playing audio chunk, ${audioQueue.length} remaining in queue`);
    playAudio(data);
  }
}

function playAudio(data) {
  const sampleRate = 16000;
  const numChannels = 1;

  console.log("client: decoding base64 data");
  const byteString = atob(data);
  const len = byteString.length;
  const uint8Array = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    uint8Array[i] = byteString.charCodeAt(i);
  }

  console.log("client: creating AudioBuffer");
  const audioBuffer = audioContext.createBuffer(numChannels, uint8Array.length / 2, sampleRate);

  console.log("client: converting PCM to float values");
  for (let channel = 0; channel < numChannels; channel++) {
    const nowBuffering = audioBuffer.getChannelData(channel);
    for (let i = 0; i < nowBuffering.length; i++) {
      const sample = (uint8Array[i * 2 + 1] << 8) | (uint8Array[i * 2] & 0xff);
      nowBuffering[i] = (sample >= 0x8000 ? sample - 0x10000 : sample) / 32768.0;
    }
  }

  console.log("client: playing audio");
  const source = audioContext.createBufferSource();
  source.buffer = audioBuffer;
  source.connect(audioContext.destination);

  // Track current audio source for interruption
  currentAudioSource = source;

  source.onended = () => {
    console.log("Audio chunk finished playing");
    if (currentAudioSource === source) {
      currentAudioSource = null;
    }
    isPlaying = false;
    playNextAudio();
  };
  source.start(0);
}

function getWebSocketURL(path = "") {
  var protocolPrefix =
    window.location.protocol === "https:" ? "wss:" : "ws:";
  var host = window.location.host;

  return protocolPrefix + "//" + host + path;
}

function addUserMessage(message) {
  userMsgDiv.innerHTML = message;
}

function addLlmMessage(response) {
  if (refreshMsgText && response) {
    llmResponseDiv.innerHTML = response;
    refreshMsgText = false;
  }
  else {
    if (response) {
      llmResponseDiv.innerHTML = llmResponseDiv.innerHTML += response;
    }
  }
}

function sendMessage() {
  let user_msg = inputField.value;
  if (user_msg) {
    let data_sent = JSON.stringify({ "user_msg": user_msg })
    chat_socket.send(data_sent)
    inputField.value = "";
    addUserMessage(user_msg);
  }
}

window.addEventListener("load", () => {
  // Initialize Session UUID and User ID
  const sessionUUID = initUUID();
  const userID = initUserID();

  const languageSelect = document.getElementById('language-select');
  if (languageSelect) {
    const savedLang = localStorage.getItem('voice_engine_language');
    if (savedLang) {
      languageSelect.value = savedLang;
      language = savedLang;
    }

    languageSelect.addEventListener('change', (e) => {
      language = e.target.value;
      localStorage.setItem('voice_engine_language', language);
      window.location.reload();
    });
  }

  const roleSelect = document.getElementById('role-select');
  if (roleSelect) {
    const savedRole = localStorage.getItem('voice_engine_role');
    if (savedRole) {
      roleSelect.value = savedRole;
      role = savedRole;
    }

    roleSelect.addEventListener('change', (e) => {
      role = e.target.value;
      localStorage.setItem('voice_engine_role', role);
      window.location.reload();
    });
  }

  // Include user_id in WebSocket URL (required for voice usage tracking)
  const websocketUrl = getWebSocketURL(`/ws/phone?language=${language}&role=${role}&session_id=${sessionUUID}&user_id=${userID}`);
  console.log({ websocketUrl, userID, sessionUUID });

  socket = new WebSocket(websocketUrl);

  socket.onopen = async () => {
    console.log('WebSocket connection opened');
    console.log(`Connected with User ID: ${userID}, Session ID: ${sessionUUID}`);
    setTimeout(() => { }, 1000)
    await start(socket);
  };

  socket.onmessage = (event) => {
    let event_parsed = JSON.parse(event.data);
    console.log(`Data-Rcvd : ${JSON.stringify(event_parsed)}`);

    // Handle voice limit notifications
    if (event_parsed.type === 'voice_limit_reached') {
      handleVoiceLimitReached(event_parsed);
      return;
    }

    if (event_parsed.type === 'voice_disabled') {
      console.log('[VOICE_DISABLED]', event_parsed.reason);
      voiceEnabled = false;
      return;
    }

    if (event_parsed.type === 'voice_usage_warning') {
      handleVoiceWarning(event_parsed);
      return;
    }

    if (event_parsed.is_text == true) {
      console.log("---> Text", { event_parsed })
      let msg = event_parsed.msg
      if (event_parsed.is_transcription == true) {
        // User's transcription - display it
        // DON'T stop audio here - let the server handle interruption via TTS
        addUserMessage(msg)
      }
      else {
        if (event_parsed.is_end) {
          refreshMsgText = true;
        }
        addLlmMessage(msg)
      }
    }
    else {
      console.log("[AUDIO_RECIEVED]", event_parsed)
      if (event_parsed.is_clear_event == true) {
        // CLEAR EVENT from server - this means user spoke and we should stop playback
        console.log("[CLEAR_BUFFER_EVENT_RECIEVED] - Stopping audio playback")
        stopAudio();
      }
      else {
        let audio_data = event_parsed.audio;
        if (audio_data) {
          console.log(`[AUDIO_QUEUED] Adding audio to queue, current queue length: ${audioQueue.length}`);
          audioQueue.push(audio_data);
          playNextAudio();
        } else {
          console.log("[AUDIO_ERROR] No audio data in message");
        }
      }
    }
  };

  socket.onclose = () => {
    console.log('WebSocket connection closed');
  };

  socket.onerror = (error) => {
    console.error('WebSocket error:', error);
  };
});