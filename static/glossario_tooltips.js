/**
 * Tooltips informativos (i) — exibe painel flutuante ao passar o mouse.
 * Funciona em cards, tabelas e áreas com overflow.
 */
(function () {
    'use strict';

    var activeTip = null;
    var activeAnchor = null;

    function escapeHtml(text) {
        return String(text || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function readContent(el) {
        var inner = el.querySelector('.tooltip-content');
        if (inner && inner.innerHTML.trim()) {
            return inner.innerHTML;
        }
        var title = el.getAttribute('data-tip-text') || el.getAttribute('title') || '';
        if (!title) return '';
        return '<p>' + escapeHtml(title) + '</p>';
    }

    function hideTip() {
        if (activeTip && activeTip.parentNode) {
            activeTip.parentNode.removeChild(activeTip);
        }
        activeTip = null;
        activeAnchor = null;
    }

    function positionTip(tip, anchor) {
        var rect = anchor.getBoundingClientRect();
        var margin = 10;
        var tipRect = tip.getBoundingClientRect();

        var top = rect.top - tipRect.height - margin;
        var left = rect.left + (rect.width / 2) - (tipRect.width / 2);

        if (top < margin) {
            top = rect.bottom + margin;
        }
        if (left < margin) {
            left = margin;
        }
        if (left + tipRect.width > window.innerWidth - margin) {
            left = window.innerWidth - tipRect.width - margin;
        }
        if (top + tipRect.height > window.innerHeight - margin) {
            top = Math.max(margin, rect.top - tipRect.height - margin);
        }

        tip.style.top = top + 'px';
        tip.style.left = left + 'px';
    }

    function showTip(el) {
        hideTip();
        var html = readContent(el);
        if (!html) return;

        var tip = document.createElement('div');
        tip.className = 'gloss-tooltip-floating';
        tip.setAttribute('role', 'tooltip');
        tip.innerHTML = html;
        document.body.appendChild(tip);

        activeTip = tip;
        activeAnchor = el;
        positionTip(tip, el);
    }

    function bindTooltip(el) {
        if (!el || el.dataset.tipBound === '1') return;
        el.dataset.tipBound = '1';

        var title = el.getAttribute('title');
        if (title && !el.getAttribute('data-tip-text')) {
            el.setAttribute('data-tip-text', title);
            el.removeAttribute('title');
        }

        el.addEventListener('mouseenter', function () { showTip(el); });
        el.addEventListener('mouseleave', hideTip);
        el.addEventListener('focus', function () { showTip(el); });
        el.addEventListener('blur', hideTip);
    }

    function initInfoTooltips(root) {
        var scope = root || document;
        scope.querySelectorAll('.info-tooltip').forEach(bindTooltip);
    }

    function onScrollOrResize() {
        if (activeTip && activeAnchor) {
            positionTip(activeTip, activeAnchor);
        }
    }

    window.refreshInfoTooltips = initInfoTooltips;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () { initInfoTooltips(); });
    } else {
        initInfoTooltips();
    }

    window.addEventListener('scroll', onScrollOrResize, true);
    window.addEventListener('resize', onScrollOrResize);
})();
