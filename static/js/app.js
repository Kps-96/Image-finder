/**
 * Drupal Media Visual & Semantic Search Engine - Client JavaScript
 * Features:
 * - Visual Search (Screenshots, Uploads, Ctrl+V, Interactive Canvas Crop)
 * - Text & Metadata Search (Search without screenshot: by name, keyword, MID, filename)
 * - URL Image Search (Search without screenshot: by remote image link)
 * - Media Library Explorer (Browse all 792 images with pagination and live search)
 * - Reverse Image Search ("Find Visually Similar Images")
 */

document.addEventListener("DOMContentLoaded", () => {
  // Navigation Tabs
  const modeTabs = document.querySelectorAll(".mode-tab");
  const tabContentVisual = document.getElementById("tabContentVisual");
  const tabContentText = document.getElementById("tabContentText");
  const tabContentUrl = document.getElementById("tabContentUrl");
  const tabContentGallery = document.getElementById("tabContentGallery");

  // Visual Tab Elements
  const dropzone = document.getElementById("dropzone");
  const dropzonePrompt = document.getElementById("dropzonePrompt");
  const cropStage = document.getElementById("cropStage");
  const fileInput = document.getElementById("fileInput");
  const cropCanvas = document.getElementById("cropCanvas");
  const ctx = cropCanvas.getContext("2d");
  const imageDimsBadge = document.getElementById("imageDimsBadge");

  const btnSearchEntire = document.getElementById("btnSearchEntire");
  const btnSearchCrop = document.getElementById("btnSearchCrop");
  const btnResetCrop = document.getElementById("btnResetCrop");
  const btnClearImage = document.getElementById("btnClearImage");
  const btnSearchTrigger = document.getElementById("btnSearchTrigger");

  const thresholdRange = document.getElementById("thresholdRange");
  const thresholdValue = document.getElementById("thresholdValue");
  const segButtons = document.querySelectorAll(".seg-btn");

  // Text Search Tab Elements
  const textSearchInput = document.getElementById("textSearchInput");
  const btnTextSearchSubmit = document.getElementById("btnTextSearchSubmit");
  const textSearchClear = document.getElementById("textSearchClear");
  const tagPills = document.querySelectorAll(".tag-pill");

  // URL Search Tab Elements
  const urlSearchInput = document.getElementById("urlSearchInput");
  const btnUrlSearchSubmit = document.getElementById("btnUrlSearchSubmit");

  // Gallery Tab Elements
  const galleryGrid = document.getElementById("galleryGrid");
  const galleryFilterInput = document.getElementById("galleryFilterInput");
  const gallerySegButtons = document.querySelectorAll(".gallery-seg-btn");
  const galleryPageInfo = document.getElementById("galleryPageInfo");
  const galleryCurrentPage = document.getElementById("galleryCurrentPage");
  const btnPrevPage = document.getElementById("btnPrevPage");
  const btnNextPage = document.getElementById("btnNextPage");

  // Results & Feedback Elements
  const resultsSection = document.getElementById("resultsSection");
  const resultsHeader = document.getElementById("resultsHeader");
  const resultsStats = document.getElementById("resultsStats");
  const resultsGrid = document.getElementById("resultsGrid");
  const emptyState = document.getElementById("emptyState");
  const loadingState = document.getElementById("loadingState");
  const loadingMessage = document.getElementById("loadingMessage");

  // Detail Modal Elements
  const modal = document.getElementById("imageModal");
  const modalClose = document.getElementById("modalClose");
  const modalBackdrop = document.getElementById("modalBackdrop");
  const modalImg = document.getElementById("modalImg");
  const modalTitle = document.getElementById("modalTitle");
  const modalMatchBadge = document.getElementById("modalMatchBadge");
  const modalMid = document.getElementById("modalMid");
  const modalBundle = document.getElementById("modalBundle");
  const modalFilename = document.getElementById("modalFilename");
  const modalDims = document.getElementById("modalDims");
  const modalSize = document.getElementById("modalSize");
  const modalAlt = document.getElementById("modalAlt");
  const modalLocalPath = document.getElementById("modalLocalPath");
  const modalBtnFindSimilar = document.getElementById("modalBtnFindSimilar");
  const modalBtnCopyPath = document.getElementById("modalBtnCopyPath");
  const modalBtnRemote = document.getElementById("modalBtnRemote");
  const modalBtnDownload = document.getElementById("modalBtnDownload");

  const themeToggle = document.getElementById("themeToggle");

  // Application State
  let activeTab = "visual";
  let rawImage = null;
  let cropSelection = null;
  let isDragging = false;
  let dragStart = { x: 0, y: 0 };
  let currentVisualFilter = "all";
  let lastSearchResults = [];

  // Gallery State
  let galleryPage = 1;
  let galleryBundle = "all";
  let gallerySearchQuery = "";
  let currentModalItem = null;

  // Theme Toggle
  themeToggle.addEventListener("click", () => {
    document.body.classList.toggle("light-theme");
  });

  // Mode Tab Navigation
  modeTabs.forEach(tab => {
    tab.addEventListener("click", () => {
      modeTabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      activeTab = tab.dataset.tab;

      tabContentVisual.style.display = activeTab === "visual" ? "flex" : "none";
      tabContentText.style.display = activeTab === "text" ? "flex" : "none";
      tabContentUrl.style.display = activeTab === "url" ? "flex" : "none";
      tabContentGallery.style.display = activeTab === "gallery" ? "flex" : "none";

      if (activeTab === "gallery") {
        resultsSection.style.display = "none";
        loadGallery(1);
      } else {
        resultsSection.style.display = "flex";
      }

      if (activeTab === "text") {
        textSearchInput.focus();
      }
    });
  });

  // Threshold Slider
  thresholdRange.addEventListener("input", (e) => {
    thresholdValue.textContent = e.target.value + "%";
  });

  // Bundle Filters for Visual Search
  segButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      segButtons.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentVisualFilter = btn.dataset.filter;
      renderResultsGrid(lastSearchResults);
    });
  });

  // ==========================================
  // TAB 1: VISUAL & SCREENSHOT SEARCH
  // ==========================================

  dropzone.addEventListener("click", (e) => {
    if (e.target.closest("#cropStage") || e.target.closest("button")) return;
    fileInput.click();
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files[0]) {
      loadImageFile(e.target.files[0]);
    }
  });

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });

  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("dragover");
  });

  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      loadImageFile(e.dataTransfer.files[0]);
    }
  });

  // Global Paste Listener (Ctrl+V)
  window.addEventListener("paste", (e) => {
    const items = (e.clipboardData || e.originalEvent.clipboardData).items;
    for (const item of items) {
      if (item.type.indexOf("image") === 0) {
        // Switch to visual tab if in text tab
        if (activeTab !== "visual") {
          modeTabs[0].click();
        }
        const file = item.getAsFile();
        loadImageFile(file);
        break;
      }
    }
  });

  function loadImageFile(file) {
    const reader = new FileReader();
    reader.onload = (evt) => {
      const img = new Image();
      img.onload = () => {
        rawImage = img;
        cropSelection = null;
        displayCropStage();
        performVisualSearch(false);
      };
      img.src = evt.target.result;
    };
    reader.readAsDataURL(file);
  }

  function displayCropStage() {
    dropzonePrompt.style.display = "none";
    cropStage.style.display = "flex";
    imageDimsBadge.textContent = `${rawImage.width} × ${rawImage.height} px`;
    btnSearchCrop.style.display = "none";
    btnResetCrop.style.display = "none";
    setupCanvas();
  }

  function setupCanvas() {
    cropCanvas.width = rawImage.width;
    cropCanvas.height = rawImage.height;
    drawCanvas();
  }

  function drawCanvas() {
    ctx.clearRect(0, 0, cropCanvas.width, cropCanvas.height);
    ctx.drawImage(rawImage, 0, 0);

    if (cropSelection) {
      ctx.fillStyle = "rgba(0, 0, 0, 0.55)";
      ctx.fillRect(0, 0, cropCanvas.width, cropSelection.y);
      ctx.fillRect(0, cropSelection.y, cropSelection.x, cropSelection.h);
      ctx.fillRect(cropSelection.x + cropSelection.w, cropSelection.y, cropCanvas.width - (cropSelection.x + cropSelection.w), cropSelection.h);
      ctx.fillRect(0, cropSelection.y + cropSelection.h, cropCanvas.width, cropCanvas.height - (cropSelection.y + cropSelection.h));

      ctx.strokeStyle = "#38bdf8";
      ctx.lineWidth = Math.max(2, Math.round(cropCanvas.width / 500));
      ctx.strokeRect(cropSelection.x, cropSelection.y, cropSelection.w, cropSelection.h);

      ctx.fillStyle = "#38bdf8";
      ctx.font = `bold ${Math.max(14, Math.round(cropCanvas.width / 60))}px Inter, sans-serif`;
      ctx.fillText(`${cropSelection.w} × ${cropSelection.h} px`, cropSelection.x + 8, cropSelection.y + 24);
    }
  }

  function getCanvasCoords(e) {
    const rect = cropCanvas.getBoundingClientRect();
    const scaleX = cropCanvas.width / rect.width;
    const scaleY = cropCanvas.height / rect.height;
    return {
      x: Math.round((e.clientX - rect.left) * scaleX),
      y: Math.round((e.clientY - rect.top) * scaleY)
    };
  }

  cropCanvas.addEventListener("mousedown", (e) => {
    isDragging = true;
    dragStart = getCanvasCoords(e);
    cropSelection = { x: dragStart.x, y: dragStart.y, w: 0, h: 0 };
    drawCanvas();
  });

  window.addEventListener("mousemove", (e) => {
    if (!isDragging) return;
    const curr = getCanvasCoords(e);
    const x = Math.min(dragStart.x, curr.x);
    const y = Math.min(dragStart.y, curr.y);
    const w = Math.abs(curr.x - dragStart.x);
    const h = Math.abs(curr.y - dragStart.y);

    cropSelection = {
      x: Math.max(0, x),
      y: Math.max(0, y),
      w: Math.min(w, cropCanvas.width - x),
      h: Math.min(h, cropCanvas.height - y)
    };
    drawCanvas();
  });

  window.addEventListener("mouseup", () => {
    if (!isDragging) return;
    isDragging = false;
    if (cropSelection && cropSelection.w > 15 && cropSelection.h > 15) {
      btnSearchCrop.style.display = "inline-flex";
      btnResetCrop.style.display = "inline-flex";
    } else {
      cropSelection = null;
      btnSearchCrop.style.display = "none";
      btnResetCrop.style.display = "none";
      drawCanvas();
    }
  });

  btnResetCrop.addEventListener("click", (e) => {
    e.stopPropagation();
    cropSelection = null;
    btnSearchCrop.style.display = "none";
    btnResetCrop.style.display = "none";
    drawCanvas();
  });

  btnClearImage.addEventListener("click", (e) => {
    e.stopPropagation();
    rawImage = null;
    cropSelection = null;
    fileInput.value = "";
    cropStage.style.display = "none";
    dropzonePrompt.style.display = "block";
    resultsGrid.innerHTML = "";
    resultsHeader.style.display = "none";
    emptyState.style.display = "block";
  });

  btnSearchEntire.addEventListener("click", (e) => {
    e.stopPropagation();
    cropSelection = null;
    btnSearchCrop.style.display = "none";
    btnResetCrop.style.display = "none";
    drawCanvas();
    performVisualSearch(false);
  });

  btnSearchCrop.addEventListener("click", (e) => {
    e.stopPropagation();
    performVisualSearch(true);
  });

  btnSearchTrigger.addEventListener("click", () => {
    if (!rawImage) {
      fileInput.click();
      return;
    }
    performVisualSearch(cropSelection !== null);
  });

  async function performVisualSearch(useCrop = false) {
    if (!rawImage) return;

    emptyState.style.display = "none";
    loadingState.style.display = "block";
    loadingMessage.textContent = "Analyzing deep neural embeddings and perceptual hashes...";
    resultsGrid.innerHTML = "";
    resultsHeader.style.display = "none";

    const threshold = parseFloat(thresholdRange.value);
    const formData = new FormData();
    formData.append("threshold", threshold);

    let blob;
    if (useCrop && cropSelection) {
      const cropOff = document.createElement("canvas");
      cropOff.width = cropSelection.w;
      cropOff.height = cropSelection.h;
      const cropCtx = cropOff.getContext("2d");
      cropCtx.drawImage(
        rawImage,
        cropSelection.x, cropSelection.y, cropSelection.w, cropSelection.h,
        0, 0, cropSelection.w, cropSelection.h
      );
      blob = await new Promise(r => cropOff.toBlob(r, "image/png"));
    } else {
      const off = document.createElement("canvas");
      off.width = rawImage.width;
      off.height = rawImage.height;
      const offCtx = off.getContext("2d");
      offCtx.drawImage(rawImage, 0, 0);
      blob = await new Promise(r => off.toBlob(r, "image/png"));
    }

    formData.append("image", blob, "query.png");

    try {
      const resp = await fetch("/api/search", { method: "POST", body: formData });
      const data = await resp.json();
      loadingState.style.display = "none";

      lastSearchResults = data.results || [];
      renderResultsGrid(lastSearchResults, data.elapsed_ms, threshold);
    } catch (err) {
      loadingState.style.display = "none";
      alert("Error performing visual search: " + err.message);
    }
  }

  // ==========================================
  // TAB 2: TEXT & KEYWORD SEARCH (NO SCREENSHOT)
  // ==========================================

  textSearchInput.addEventListener("input", () => {
    textSearchClear.style.display = textSearchInput.value ? "block" : "none";
  });

  textSearchClear.addEventListener("click", () => {
    textSearchInput.value = "";
    textSearchClear.style.display = "none";
    textSearchInput.focus();
  });

  textSearchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      performTextSearch();
    }
  });

  btnTextSearchSubmit.addEventListener("click", performTextSearch);

  tagPills.forEach(pill => {
    pill.addEventListener("click", () => {
      textSearchInput.value = pill.dataset.q;
      textSearchClear.style.display = "block";
      performTextSearch();
    });
  });

  async function performTextSearch() {
    const q = textSearchInput.value.trim();
    if (!q) {
      textSearchInput.focus();
      return;
    }

    emptyState.style.display = "none";
    loadingState.style.display = "block";
    loadingMessage.textContent = `Searching metadata across 792 Drupal assets for "${q}"...`;
    resultsGrid.innerHTML = "";
    resultsHeader.style.display = "none";

    try {
      const resp = await fetch("/api/search_text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q, threshold: 50.0, top_k: 40 })
      });
      const data = await resp.json();
      loadingState.style.display = "none";

      lastSearchResults = data.results || [];
      renderResultsGrid(lastSearchResults, data.elapsed_ms, null, `Text query: "${q}"`);
    } catch (err) {
      loadingState.style.display = "none";
      alert("Error performing text search: " + err.message);
    }
  }

  // ==========================================
  // TAB 3: SEARCH BY URL (NO SCREENSHOT)
  // ==========================================

  urlSearchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") performUrlSearch();
  });

  btnUrlSearchSubmit.addEventListener("click", performUrlSearch);

  async function performUrlSearch() {
    const url = urlSearchInput.value.trim();
    if (!url) {
      urlSearchInput.focus();
      return;
    }

    emptyState.style.display = "none";
    loadingState.style.display = "block";
    loadingMessage.textContent = "Fetching remote image and extracting visual signatures...";
    resultsGrid.innerHTML = "";
    resultsHeader.style.display = "none";

    const threshold = parseFloat(thresholdRange.value);

    try {
      const resp = await fetch("/api/search_url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url, threshold: threshold, top_k: 30 })
      });
      const data = await resp.json();
      loadingState.style.display = "none";

      if (data.error) {
        alert(data.error);
        emptyState.style.display = "block";
        return;
      }

      lastSearchResults = data.results || [];
      renderResultsGrid(lastSearchResults, data.elapsed_ms, threshold, `URL: ${url}`);
    } catch (err) {
      loadingState.style.display = "none";
      alert("Error performing URL image search: " + err.message);
    }
  }

  // ==========================================
  // TAB 4: MEDIA GALLERY EXPLORER
  // ==========================================

  gallerySegButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      gallerySegButtons.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      galleryBundle = btn.dataset.gfilter;
      galleryPage = 1;
      loadGallery(1);
    });
  });

  let galleryDebounceTimer = null;
  galleryFilterInput.addEventListener("input", (e) => {
    clearTimeout(galleryDebounceTimer);
    galleryDebounceTimer = setTimeout(() => {
      gallerySearchQuery = e.target.value.trim();
      galleryPage = 1;
      loadGallery(1);
    }, 250);
  });

  btnPrevPage.addEventListener("click", () => {
    if (galleryPage > 1) {
      loadGallery(galleryPage - 1);
    }
  });

  btnNextPage.addEventListener("click", () => {
    loadGallery(galleryPage + 1);
  });

  async function loadGallery(page) {
    galleryGrid.innerHTML = `
      <div class="loading-state" style="grid-column: 1 / -1;">
        <div class="spinner"></div>
        <p>Loading library assets...</p>
      </div>
    `;

    try {
      const params = new URLSearchParams({
        page: page,
        per_page: 36,
        bundle: galleryBundle,
        q: gallerySearchQuery
      });
      const resp = await fetch(`/api/gallery?${params.toString()}`);
      const data = await resp.json();

      galleryPage = data.page;
      const totalPages = data.total_pages;

      galleryCurrentPage.textContent = `Page ${galleryPage} of ${totalPages}`;
      btnPrevPage.disabled = galleryPage <= 1;
      btnNextPage.disabled = galleryPage >= totalPages;

      const start = (galleryPage - 1) * data.per_page + 1;
      const end = Math.min(galleryPage * data.per_page, data.total);
      galleryPageInfo.textContent = `Showing ${start}-${end} of ${data.total} assets`;

      renderGalleryCards(data.items);
    } catch (err) {
      galleryGrid.innerHTML = `<div class="empty-state" style="grid-column: 1 / -1;"><p>Failed to load gallery: ${err.message}</p></div>`;
    }
  }

  function renderGalleryCards(items) {
    galleryGrid.innerHTML = "";
    if (items.length === 0) {
      galleryGrid.innerHTML = `
        <div class="empty-state" style="grid-column: 1 / -1;">
          <div class="empty-icon">📁</div>
          <h3>No Media Found</h3>
          <p>No assets match your current gallery filter.</p>
        </div>
      `;
      return;
    }

    items.forEach(item => {
      const meta = item.meta;
      const webUrl = item.web_url;

      const card = document.createElement("div");
      card.className = "media-card";
      card.innerHTML = `
        <div class="card-thumb-wrapper" title="Click to view details">
          <img class="card-thumb" src="${webUrl}" alt="${escapeHtml(meta.name)}" loading="lazy">
        </div>
        <div class="card-body">
          <div class="card-meta-row">
            <span class="mid-tag">MID: ${meta.media_id}</span>
            <span class="bundle-tag">${meta.bundle === 'svg_image' ? 'SVG' : 'Image'}</span>
          </div>
          <h4 class="card-title">${escapeHtml(meta.name)}</h4>
          <div class="card-details">
            <div class="truncate-text" title="${escapeHtml(meta.filename)}">📄 ${escapeHtml(meta.filename)}</div>
            <div>📐 ${meta.width || '?'} &times; ${meta.height || '?'} px &middot; ${formatBytes(meta.downloaded_size)}</div>
          </div>
          <div class="card-actions">
            <button class="btn btn-secondary btn-find-similar" data-mid="${meta.media_id}" title="Reverse image search">🔍 Find Similar</button>
            <button class="btn btn-outline btn-gallery-detail">Details</button>
          </div>
        </div>
      `;

      card.querySelector(".card-thumb-wrapper").addEventListener("click", () => openModal({ meta: meta, web_url: webUrl, score: 100 }));
      card.querySelector(".btn-gallery-detail").addEventListener("click", () => openModal({ meta: meta, web_url: webUrl, score: 100 }));

      card.querySelector(".btn-find-similar").addEventListener("click", (e) => {
        e.stopPropagation();
        triggerReverseSearch(meta.media_id, meta.name);
      });

      galleryGrid.appendChild(card);
    });
  }

  // Reverse Image Search
  async function triggerReverseSearch(mediaId, mediaName) {
    modal.style.display = "none";
    modeTabs[0].click(); // Switch to results view

    emptyState.style.display = "none";
    loadingState.style.display = "block";
    loadingMessage.textContent = `Finding visually similar images to "${mediaName}" (MID: ${mediaId})...`;
    resultsGrid.innerHTML = "";
    resultsHeader.style.display = "none";

    try {
      const resp = await fetch(`/api/similar/${mediaId}?threshold=65.0`);
      const data = await resp.json();
      loadingState.style.display = "none";

      lastSearchResults = data.results || [];
      renderResultsGrid(lastSearchResults, data.elapsed_ms, 65.0, `Visual similarity to: "${mediaName}" (MID ${mediaId})`);
    } catch (err) {
      loadingState.style.display = "none";
      alert("Error finding similar images: " + err.message);
    }
  }

  // ==========================================
  // RESULTS RENDERING & MODAL
  // ==========================================

  function renderResultsGrid(results, elapsedMs = null, threshold = null, queryLabel = "") {
    resultsHeader.style.display = "flex";
    resultsGrid.innerHTML = "";

    const activeThreshold = threshold !== null ? threshold : parseFloat(thresholdRange.value);

    let filtered = results;
    if (activeTab === "visual" && currentVisualFilter !== "all") {
      filtered = results.filter(r => r.meta.bundle === currentVisualFilter);
    }

    const msText = elapsedMs ? ` in ${elapsedMs} ms` : "";
    const labelText = queryLabel ? ` &middot; ${queryLabel}` : "";
    resultsStats.innerHTML = `Found <strong>${filtered.length}</strong> matches (Indexed: 792 items)${msText}${labelText}`;

    if (filtered.length === 0) {
      resultsGrid.innerHTML = `
        <div class="empty-state" style="grid-column: 1 / -1; margin: 1rem 0;">
          <div class="empty-icon">🔎</div>
          <h3>No Matches Found</h3>
          <p>Try lowering the similarity threshold or switching to <strong>Search by Text</strong> to find images by keyword.</p>
        </div>
      `;
      return;
    }

    filtered.forEach((item) => {
      const meta = item.meta;
      const score = item.score;
      const webUrl = item.web_url;
      const isSuper = score >= 95.0;
      const isTextMatch = item.match_type === "text";

      const card = document.createElement("div");
      card.className = "media-card";
      card.innerHTML = `
        <div class="card-thumb-wrapper" title="Click to view details">
          <img class="card-thumb" src="${webUrl}" alt="${escapeHtml(meta.name)}" loading="lazy">
          <div class="match-badge ${isTextMatch ? 'text-match' : (isSuper ? 'super' : 'high')}">
            <span>${isTextMatch ? '✓ ' + score + '% MATCH' : score + '% MATCH'}</span>
          </div>
        </div>
        <div class="card-body">
          <div class="card-meta-row">
            <span class="mid-tag">MID: ${meta.media_id}</span>
            <span class="bundle-tag">${meta.bundle === 'svg_image' ? 'SVG Graphic' : 'Image'}</span>
          </div>
          <h4 class="card-title">${escapeHtml(meta.name)}</h4>
          <div class="card-details">
            <div class="truncate-text" title="${escapeHtml(meta.filename)}">📄 ${escapeHtml(meta.filename)}</div>
            <div>📐 ${meta.width || '?'} &times; ${meta.height || '?'} px &middot; ${formatBytes(meta.downloaded_size)}</div>
            ${item.match_reason ? `<div style="color: #a855f7; font-size: 0.8rem;">💡 ${escapeHtml(item.match_reason)}</div>` : ''}
          </div>
          <div class="card-actions">
            <button class="btn btn-secondary btn-detail">Details</button>
            <button class="btn btn-secondary btn-card-similar" title="Find visually similar images">🔍 Similar</button>
            <a href="${webUrl}" target="_blank" class="btn btn-outline" title="Open high-res in new tab">View</a>
          </div>
        </div>
      `;

      card.querySelector(".card-thumb-wrapper").addEventListener("click", () => openModal(item));
      card.querySelector(".btn-detail").addEventListener("click", () => openModal(item));
      card.querySelector(".btn-card-similar").addEventListener("click", (e) => {
        e.stopPropagation();
        triggerReverseSearch(meta.media_id, meta.name);
      });

      resultsGrid.appendChild(card);
    });
  }

  function openModal(item) {
    currentModalItem = item;
    const meta = item.meta;
    modalImg.src = item.web_url;
    modalTitle.textContent = meta.name;
    modalMatchBadge.textContent = `${item.score}% SIMILARITY MATCH`;
    modalMatchBadge.className = `modal-match-badge ${item.score >= 95 ? 'super' : 'high'}`;

    modalMid.textContent = meta.media_id || "-";
    modalBundle.textContent = meta.bundle === 'svg_image' ? 'SVG Vector Graphic' : 'Raster Image';
    modalFilename.textContent = meta.filename || "-";
    modalDims.textContent = `${meta.width || '?'} × ${meta.height || '?'} px`;
    modalSize.textContent = formatBytes(meta.downloaded_size);
    modalAlt.textContent = meta.alt || "None";
    modalLocalPath.textContent = meta.local_rel_path;

    modalBtnFindSimilar.onclick = () => {
      triggerReverseSearch(meta.media_id, meta.name);
    };

    modalBtnCopyPath.onclick = () => {
      navigator.clipboard.writeText(meta.local_rel_path);
      modalBtnCopyPath.textContent = "✓ Copied Path!";
      setTimeout(() => modalBtnCopyPath.textContent = "📋 Copy Local Path", 2000);
    };

    if (meta.remote_url) {
      modalBtnRemote.href = meta.remote_url;
      modalBtnRemote.style.display = "inline-flex";
    } else {
      modalBtnRemote.style.display = "none";
    }

    modalBtnDownload.href = item.web_url;
    modalBtnDownload.download = meta.filename;

    modal.style.display = "flex";
  }

  modalClose.addEventListener("click", () => modal.style.display = "none");
  modalBackdrop.addEventListener("click", () => modal.style.display = "none");
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modal.style.display === "flex") {
      modal.style.display = "none";
    }
  });

  function formatBytes(bytes) {
    if (!bytes || bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  }

  function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
});
