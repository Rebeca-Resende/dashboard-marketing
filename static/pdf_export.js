/**
 * Modulo de Exportacao PDF para o Sindibor Dashboard
 * Corrigido para:
 * 1) capturar abas ocultas com dimensao real
 * 2) evitar corte do conteudo em paginas longas
 * 3) melhorar nitidez da exportacao
 */

window.syncPdfDatesToGlobal = function() {
    const globalStart = document.getElementById('global-start-date')?.value || '';
    const globalEnd = document.getElementById('global-end-date')?.value || '';
    const pdfStartInput = document.getElementById('pdf-start-date');
    const pdfEndInput = document.getElementById('pdf-end-date');

    if (pdfStartInput && globalStart) pdfStartInput.value = globalStart;
    if (pdfEndInput && globalEnd) pdfEndInput.value = globalEnd;
};

function convertCanvasesToImages(root) {
    const replacements = [];
    if (typeof Chart !== 'undefined') {
        root.querySelectorAll('canvas').forEach(canvas => {
            const chart = Chart.getChart(canvas);
            if (chart) {
                chart.resize();
                chart.update('none');
            }
        });
    }

    root.querySelectorAll('canvas').forEach(canvas => {
        try {
            const img = document.createElement('img');
            img.src = canvas.toDataURL('image/png');
            const rect = canvas.getBoundingClientRect();
            img.style.width = Math.max(rect.width, canvas.offsetWidth || 0) + 'px';
            img.style.height = Math.max(rect.height, canvas.offsetHeight || 0) + 'px';
            img.style.display = 'block';
            img.className = (canvas.className || '') + ' canvas-export-image';
            canvas.parentNode.insertBefore(img, canvas);
            canvas.style.display = 'none';
            replacements.push({ canvas, img });
        } catch (err) {
            console.warn('Falha ao converter canvas para imagem:', err);
        }
    });
    return replacements;
}

function restoreCanvasesFromImages(replacements) {
    replacements.forEach(({ canvas, img }) => {
        canvas.style.display = '';
        if (img && img.parentNode) img.parentNode.removeChild(img);
    });
}

function wait(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function forceTabVisible(targetTab, allTabs) {
    allTabs.forEach(tab => {
        tab.classList.remove('active');
        tab.style.setProperty('display', 'none', 'important');
        tab.style.setProperty('visibility', 'hidden', 'important');
        tab.style.setProperty('position', 'absolute', 'important');
        tab.style.setProperty('left', '-99999px', 'important');
        tab.style.setProperty('top', '0', 'important');
        tab.style.setProperty('height', 'auto', 'important');
        tab.style.setProperty('overflow', 'visible', 'important');
    });

    targetTab.classList.add('active');
    targetTab.style.setProperty('display', 'block', 'important');
    targetTab.style.setProperty('visibility', 'visible', 'important');
    targetTab.style.setProperty('position', 'relative', 'important');
    targetTab.style.setProperty('left', '0', 'important');
    targetTab.style.setProperty('top', '0', 'important');
    targetTab.style.setProperty('height', 'auto', 'important');
    targetTab.style.setProperty('overflow', 'visible', 'important');
}

function restoreTabs(allTabs, originalStates, currentActiveTab) {
    allTabs.forEach((tab, index) => {
        const state = originalStates[index];
        if (!state) return;
        tab.className = state.className;
        tab.setAttribute('style', state.style);
    });

    if (currentActiveTab && !currentActiveTab.classList.contains('active')) {
        currentActiveTab.classList.add('active');
    }
}

function addCanvasAsPaginatedImage(pdf, canvas, title, opts = {}) {
    const margin = opts.margin ?? 10;
    const titleGap = opts.titleGap ?? 12;
    const titleTop = opts.titleTop ?? 15;

    const pageWidth = pdf.internal.pageSize.getWidth();
    const pageHeight = pdf.internal.pageSize.getHeight();
    const usableWidth = pageWidth - (margin * 2);
    const usableHeightFirstPage = pageHeight - margin - (margin + titleGap);
    const usableHeightOtherPages = pageHeight - (margin * 2);

    const canvasWidth = canvas.width;
    const canvasHeight = canvas.height;

    const mmPerPx = usableWidth / canvasWidth;
    const pageSliceHeightPxFirst = Math.floor(usableHeightFirstPage / mmPerPx);
    const pageSliceHeightPxOther = Math.floor(usableHeightOtherPages / mmPerPx);

    let renderedHeightPx = 0;
    let firstPage = true;

    while (renderedHeightPx < canvasHeight) {
        const remainingHeightPx = canvasHeight - renderedHeightPx;
        const sliceHeightPx = Math.min(
            firstPage ? pageSliceHeightPxFirst : pageSliceHeightPxOther,
            remainingHeightPx
        );

        const pageCanvas = document.createElement('canvas');
        pageCanvas.width = canvasWidth;
        pageCanvas.height = sliceHeightPx;

        const ctx = pageCanvas.getContext('2d', { alpha: false });
        ctx.fillStyle = '#FFFFFF';
        ctx.fillRect(0, 0, pageCanvas.width, pageCanvas.height);
        ctx.drawImage(
            canvas,
            0,
            renderedHeightPx,
            canvasWidth,
            sliceHeightPx,
            0,
            0,
            canvasWidth,
            sliceHeightPx
        );

        const imgData = pageCanvas.toDataURL('image/png');
        const renderedHeightMm = sliceHeightPx * mmPerPx;

        if (!firstPage) {
            pdf.addPage();
        } else {
            pdf.setFontSize(16);
            pdf.setTextColor(234, 98, 28);
            pdf.text(title, margin, titleTop);
        }

        const yPos = firstPage ? (margin + titleGap) : margin;
        pdf.addImage(imgData, 'PNG', margin, yPos, usableWidth, renderedHeightMm, undefined, 'FAST');

        renderedHeightPx += sliceHeightPx;
        firstPage = false;
    }
}

window.exportDashboardToPDF = async function() {
    const btn = document.querySelector('.btn-pdf-export');
    const pdfStart = document.getElementById('pdf-start-date')?.value || '';
    const pdfEnd = document.getElementById('pdf-end-date')?.value || '';

    if (!btn) {
        alert('Botao de exportacao PDF nao encontrado.');
        return;
    }

    if (pdfStart || pdfEnd) {
        const globalStart = document.getElementById('global-start-date');
        const globalEnd = document.getElementById('global-end-date');
        if (globalStart) globalStart.value = pdfStart;
        if (globalEnd) globalEnd.value = pdfEnd;

        if (typeof window.applyGlobalFilter === 'function') {
            window.applyGlobalFilter();
            await wait(1800);
        }
    }

    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Gerando PDF...';
    btn.disabled = true;

    try {
        if (!window.jspdf || !window.jspdf.jsPDF || typeof html2canvas !== 'function') {
            throw new Error('Bibliotecas jsPDF/html2canvas nao encontradas.');
        }

        const { jsPDF } = window.jspdf;
        const pdf = new jsPDF('p', 'mm', 'a4');

        const selectedPages = [];
        document.querySelectorAll('.page-checkbox:checked').forEach(cb => {
            selectedPages.push({ id: cb.value, name: cb.dataset.name || cb.value });
        });

        if (selectedPages.length === 0) {
            alert('Selecione pelo menos uma pagina.');
            return;
        }

        const currentActiveTab = document.querySelector('.tab-content.active');
        const allTabs = Array.from(document.querySelectorAll('.tab-content'));
        const originalStates = allTabs.map(tab => ({
            className: tab.className,
            style: tab.getAttribute('style') || ''
        }));

        let isFirstSelectedPage = true;

        for (const page of selectedPages) {
            const targetTab = document.getElementById(page.id);
            if (!targetTab) continue;

            if (!isFirstSelectedPage) {
                pdf.addPage();
            }

            forceTabVisible(targetTab, allTabs);

            if (typeof window.refreshAllChartsLayout === 'function') {
                window.refreshAllChartsLayout();
            }
            await wait(800);

            const rect = targetTab.getBoundingClientRect();
            const captureWidth = Math.ceil(Math.max(
                targetTab.scrollWidth,
                targetTab.offsetWidth,
                rect.width,
                document.documentElement.clientWidth,
                1400
            ));
            const captureHeight = Math.ceil(Math.max(
                targetTab.scrollHeight,
                targetTab.offsetHeight,
                rect.height
            ));

            const canvasReplacements = convertCanvasesToImages(targetTab);

            const canvas = await html2canvas(targetTab, {
                scale: Math.min(window.devicePixelRatio || 1, 2) * 2,
                useCORS: true,
                allowTaint: false,
                backgroundColor: '#FFFFFF',
                logging: false,
                width: captureWidth,
                height: captureHeight,
                windowWidth: captureWidth,
                windowHeight: captureHeight,
                scrollX: 0,
                scrollY: -window.scrollY
            });

            restoreCanvasesFromImages(canvasReplacements);
            addCanvasAsPaginatedImage(pdf, canvas, page.name);
            isFirstSelectedPage = false;
        }

        restoreTabs(allTabs, originalStates, currentActiveTab);
        pdf.save(`Sindibor_Dashboard_${new Date().toISOString().slice(0, 10)}.pdf`);
    } catch (error) {
        console.error('Erro ao gerar PDF:', error);
        alert(`Erro ao gerar PDF: ${error.message || error}`);
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
};
