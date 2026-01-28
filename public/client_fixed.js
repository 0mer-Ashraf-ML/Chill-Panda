let chat_socket;
let language = "en";
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

// FIXED: Properly stop all audio including currently playing
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
  
  // FIXED: Track current audio source for interruption
  currentAudioSource = source;
  
  source.onended = () => {
    console.log("Audio chunk finished playing");
    // Only mark as not playing if this is still the current source
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
  const sessionUUID = initUUID();

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

  // Use 'web' source for browser MediaRecorder (WebM/Opus format)
  const websocketUrl = getWebSocketURL(`/ws/web?language=${language}&session_id=${sessionUUID}`);
  console.log({ websocketUrl });

  socket = new WebSocket(websocketUrl);

  socket.onopen = async () => {
    console.log('WebSocket connection opened');
    setTimeout(() => { }, 1000)
    await start(socket);
  };

  socket.onmessage = (event) => {
    let event_parsed = JSON.parse(event.data);
    console.log(`Data-Rcvd : ${JSON.stringify(event_parsed)}`);

    if (event_parsed.is_text == true) {
      console.log("---> Text", { event_parsed })
      let msg = event_parsed.msg
      if (event_parsed.is_transcription == true) {
        // FIXED: Stop any playing audio when user speaks (detected via transcription)
        stopAudio();
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
        console.log("[CLEAR_BUFFER_EVENT_RECIEVED] - Clearing audio queue and stopping playback")
        // FIXED: Actually stop the audio, not just clear queue
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