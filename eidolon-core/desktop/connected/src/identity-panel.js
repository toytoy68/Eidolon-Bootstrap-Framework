/* ==========================================================
 * Projet      : Eidolon Core
 * Organisation: Eidolon Core Technologies (ECT)
 * Fichier     : identity-panel.js
 * Description : Enrôlement volontaire du profil connecté, sans changement de droits
 * Standard    : Eidolon Presentation Standard v1
 * ========================================================== */
(function (root) {
  "use strict";
  function mount(doc, conv, deps) {
    var $ = function (id) { return doc.getElementById("identity-" + id); };
    if (!$("panel")) return null;
    var generation = 0, session = null, flow = null, status = null, busy = false;
    var stream = null, recorder = null, timer = null, captureMode = null, deleteApproval = null;
    function key() { var a = new Uint8Array(16); root.crypto.getRandomValues(a); return Array.from(a, function (b) { return b.toString(16).padStart(2,"0"); }).join(""); }
    function stopStream(s) { if (s && s.getTracks) s.getTracks().forEach(function (t) { t.stop(); }); }
    function config() { return status && status.modalities.find(function (m) { return m.modality === $("modality").value; }); }
    function render() {
      var c = config(), collecting = flow && flow.state === "COLLECTING";
      $("begin").disabled = busy || !c || c.enrolled || collecting;
      $("capture").disabled = busy || !collecting || !!flow.approval_sha256;
      $("capture").textContent = recorder ? "Terminer la prise" : "Prendre un échantillon";
      $("confirm").hidden = !collecting || !flow.approval_sha256;
      $("confirm").disabled = busy;
      $("cancel").hidden = !collecting && !stream && !busy;
      $("probe").disabled = busy || !c || !c.enrolled;
      $("delete").disabled = busy || !c || !c.enrolled;
      $("delete-confirm").hidden = !deleteApproval;
      $("modality").disabled = busy || !!collecting || !!stream;
      $("indicator").textContent = stream ? "Capture en cours — capteur actif" : busy ? "Traitement en cours — capteur arrêté" : "Capteurs arrêtés";
      $("indicator").className = stream ? "comm-indicator recording" : "comm-indicator off";
      $("progress").textContent = flow ? flow.state + " · " + flow.samples + "/" + flow.required + " prises" : "";
    }
    function stopCapture() {
      if (timer !== null) { deps.clearTimeout(timer); timer = null; }
      if (recorder) { recorder.cancel(); recorder = null; }
      stopStream(stream); stream = null;
      if (deps.afterCapture) deps.afterCapture();
    }
    function reset() {
      generation++; stopCapture(); busy = false; flow = status = deleteApproval = null;
      $("output").textContent = ""; $("present").checked = $("consent").checked = false;
      $("modality").textContent = ""; render();
    }
    async function post(route, body) {
      var mine = generation;
      var answer = await conv.service("identity_" + route, body);
      if (mine !== generation || answer.stale) return null;
      if (!answer.ok) { $("output").textContent = "Opération non confirmée : " + answer.code + ". Actualisez l’état avant de recommencer."; return null; }
      return answer.json;
    }
    async function refresh() {
      var result = await post("status", {});
      if (!result) return;
      status = result;
      var selected = $("modality").value;
      $("modality").textContent = "";
      status.modalities.forEach(function (m) { var o = doc.createElement("option"); o.value=m.modality;
        o.textContent=(m.modality === "voice" ? "Voix" : "Visage") + (m.enrolled ? " — enregistré" : " — non enregistré") + (m.calibrated ? "" : " — non calibré"); $("modality").appendChild(o); });
      if (status.modalities.some(function (m) { return m.modality === selected; })) $("modality").value = selected;
      flow = status.sessions.find(function (s) { return s.state === "COLLECTING" && s.modality === $("modality").value; }) || null;
      render();
    }
    function consent() {
      if (!$("present").checked || !$("consent").checked) {
        $("output").textContent = "Confirmez votre présence et votre accord avant une capture."; return false;
      }
      return true;
    }
    async function submitCapture(bytes, mine, mode) {
      if (mine !== generation) { bytes.fill(0); return; }
      if (!bytes.length || bytes.length > 512*1024) { bytes.fill(0); $("output").textContent="Capture vide ou trop volumineuse."; return; }
      var binary = "";
      for (var i=0; i<bytes.length; i+=8192) binary += String.fromCharCode.apply(null,bytes.subarray(i,i+8192));
      bytes.fill(0);
      busy=true; render();
      var body = {capture_base64:root.btoa(binary)};
      binary="";
      if (mode === "probe") body.modality=$("modality").value;
      else { body.session_id=flow.session_id; body.sample_key=key(); }
      var result=await post(mode === "probe" ? "probe" : "sample",body);
      body.capture_base64="";
      if (mine !== generation) return;
      busy=false;
      if (result) {
        if (mode === "probe") $("output").textContent = result.authorizes_execution === false && Array.isArray(result.grants) && !result.grants.length ?
          "Comparaison au seul profil connecté : " + result.state + ". Résultat non vérifié, aucun droit accordé." : "Résultat refusé : revendication de droits.";
        else { flow=result; $("output").textContent=result.approval_sha256 ? "Prises reçues. Confirmez leur enregistrement, ou annulez." : "Prise reçue ; poursuivez avec une nouvelle prise."; }
      }
      render();
    }
    async function finishVoice() {
      if (!recorder) return;
      var active=recorder, mine=generation, mode=captureMode; recorder=null;
      if (timer !== null) deps.clearTimeout(timer); timer=null;
      stopStream(stream); stream=null; busy=true; render();
      try {
        var audio=await active.stop();
        if (mine !== generation) { audio.samples.fill(0); return; }
        var bytes=root.EidolonCommunication.encodeWav(audio.samples,audio.rate).slice(44);
        audio.samples.fill(0); await submitCapture(bytes,mine,mode);
      } catch (_) { if (mine === generation) $("output").textContent="Prise interrompue."; }
      finally { if (mine === generation) { busy=false;if(deps.afterCapture)deps.afterCapture();render(); } }
    }
    async function capture(mode) {
      if (recorder) { await finishVoice(); return; }
      if (busy || !consent() || !config()) return;
      var mine=generation, modality=$("modality").value;
      captureMode=mode; busy=true; render();
      if (deps.beforeCapture) deps.beforeCapture();
      try {
        var acquired=await deps.media.getUserMedia(modality === "voice" ? {audio:{channelCount:1}} : {video:{width:{max:1280},height:{max:720}}});
        if (mine !== generation) { stopStream(acquired); return; }
        stream=acquired; render();
        if (modality === "voice") {
          recorder=deps.recorder(stream); busy=false;
          timer=deps.setTimeout(finishVoice,config().max_duration_s*1000);
          $("output").textContent="Parlez distinctement, une seule personne. Minimum de parole configuré : " + config().min_speech_s + " s.";
          render(); return;
        }
        var image;
        try { image=await deps.grabFrame(stream); } finally { stopStream(acquired); if (stream === acquired) stream=null; }
        await submitCapture(image,mine,mode);
      } catch (_) { if (mine === generation) { stopCapture(); $("output").textContent="Capture indisponible ou permission refusée."; } }
      finally { if (mine === generation && !recorder) { busy=false;if(deps.afterCapture)deps.afterCapture();render(); } }
    }
    $("refresh").addEventListener("click",function(){ if(!busy) refresh(); });
    $("modality").addEventListener("change",function(){ flow=null;deleteApproval=null;render(); });
    $("begin").addEventListener("click",async function(){
      if(busy || !consent())return; var mine=generation;busy=true;render();
      var result=await post("begin",{modality:$("modality").value,request_key:key(),present:true,consent:true});
      if(mine!==generation)return;busy=false;if(result)flow=result;render();
    });
    $("capture").addEventListener("click",function(){capture("sample");});
    $("probe").addEventListener("click",function(){capture("probe");});
    $("cancel").addEventListener("click",async function(){
      var old=flow;generation++;stopCapture();busy=false;flow=null;deleteApproval=null;render();
      if(old && old.state==="COLLECTING")await post("cancel",{session_id:old.session_id});
      await refresh();
    });
    $("confirm").addEventListener("click",async function(){
      if(busy || !flow || !flow.approval_sha256)return;var mine=generation;busy=true;render();
      var result=await post("confirm",{session_id:flow.session_id,sha256:flow.approval_sha256});
      if(mine!==generation)return;busy=false;
      if(result){flow=null;$("output").textContent="Gabarits enregistrés pour le profil connecté. Aucun droit accordé.";await refresh();}render();
    });
    $("delete").addEventListener("click",function(){
      if(busy || !config() || !config().delete_sha256)return;
      deleteApproval={modality:$("modality").value,sha256:config().delete_sha256};
      $("output").textContent="Confirmer le retrait des gabarits actifs ? Les anciennes sauvegardes ne seront pas effacées.";render();
    });
    $("delete-confirm").addEventListener("click",async function(){
      if(busy || !deleteApproval)return;var mine=generation;busy=true;render();
      var result=await post("delete",deleteApproval);
      if(mine!==generation)return;busy=false;deleteApproval=null;
      if(result){$("output").textContent="Gabarits retirés du registre actif ; anciennes sauvegardes conservées.";await refresh();}render();
    });
    render();
    return {beforeClose:function(){
      if(flow && flow.state==="COLLECTING")conv.service("identity_cancel",{session_id:flow.session_id});
      reset();
    },update:function(state){
      var next=state.phase==="open" && state.services && state.services.identity_enrolment ? state.conversationId : null;
      $("panel").hidden=!next;
      if(next!==session){reset();session=next;if(next)refresh();}
    }};
  }
  var api={mount:mount};
  if(typeof module==="object" && module.exports)module.exports=api;else root.EidolonIdentityPanel=api;
})(typeof window!=="undefined"?window:this);
