(function () {
  'use strict';

  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const navbar = document.querySelector('.navbar');
  const hamburger = document.querySelector('.hamburger');
  const mobileMenu = document.querySelector('.mobile-menu');
  const mobileClose = document.querySelector('.mobile-menu-close');
  const themeToggle = document.getElementById('theme-toggle');
  const NAV_OPACITY_MIN = 0.72;
  const NAV_OPACITY_MAX = 0.96;
  const NAV_OPACITY_SCROLL_RANGE = 420;
  const RIPPLE_DURATION_MS = 600;
  const rippleTimeoutIds = new Set();

  // Theme Toggle Logic
  const initializeTheme = () => {
    const savedTheme = localStorage.getItem('theme');
    const theme = savedTheme || 'dark'; // Default to dark
    document.documentElement.setAttribute('data-theme', theme);
  };

  const toggleTheme = () => {
    const html = document.documentElement;
    const currentTheme = html.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    html.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
  };

  if (themeToggle) {
    themeToggle.addEventListener('click', toggleTheme);
  }

  initializeTheme();

  const setNavbarState = () => {
    if (!navbar) return;
    const scrolled = window.scrollY > 40;
    navbar.classList.toggle('scrolled', scrolled);
    const dynamicOpacity = Math.min(
      NAV_OPACITY_MAX,
      NAV_OPACITY_MIN + (window.scrollY / NAV_OPACITY_SCROLL_RANGE) * (NAV_OPACITY_MAX - NAV_OPACITY_MIN)
    );
    navbar.style.setProperty('--nav-opacity', dynamicOpacity.toFixed(2));
  };

  const closeMenu = () => {
    if (!hamburger || !mobileMenu) return;
    hamburger.classList.remove('open');
    hamburger.setAttribute('aria-expanded', 'false');
    mobileMenu.classList.remove('open');
    document.body.classList.remove('menu-open');
  };

  const openMenu = () => {
    if (!hamburger || !mobileMenu) return;
    hamburger.classList.add('open');
    hamburger.setAttribute('aria-expanded', 'true');
    mobileMenu.classList.add('open');
    document.body.classList.add('menu-open');
  };

  setNavbarState();
  let navTicking = false;
  window.addEventListener(
    'scroll',
    () => {
      if (navTicking) return;
      navTicking = true;
      window.requestAnimationFrame(() => {
        setNavbarState();
        navTicking = false;
      });
    },
    { passive: true }
  );

  if (hamburger && mobileMenu) {
    hamburger.addEventListener('click', () => {
      const isOpen = mobileMenu.classList.contains('open');
      if (isOpen) closeMenu();
      else openMenu();
    });
    mobileMenu.querySelectorAll('a').forEach((a) => a.addEventListener('click', closeMenu));
    if (mobileClose) mobileClose.addEventListener('click', closeMenu);
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') closeMenu();
    });
  }

  document.querySelectorAll('.field-toggle').forEach((button) => {
    button.addEventListener('click', () => {
      const wrap = button.closest('.field-wrapper');
      const input = wrap ? wrap.querySelector('input') : null;
      if (!input) return;
      const show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      button.textContent = show ? 'Hide' : 'Show';
      button.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
    });
  });

  const currentPath = window.location.pathname;
  document.querySelectorAll('.navbar-links a, .mobile-menu a').forEach((link) => {
    const href = link.getAttribute('href');
    if (!href) return;
    const exact = href === '/' && currentPath === '/';
    const starts = href !== '/' && currentPath.startsWith(href);
    if (exact || starts) link.classList.add('active');
  });

  document.querySelectorAll('a[href^="#"]').forEach((link) => {
    link.addEventListener('click', (e) => {
      const target = document.querySelector(link.getAttribute('href'));
      if (!target) return;
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });

  const initRipples = () => {
    document.querySelectorAll('.ripple-target').forEach((el) => {
      el.addEventListener('click', (e) => {
        const rect = el.getBoundingClientRect();
        const ripple = document.createElement('span');
        ripple.className = 'ripple';
        ripple.style.left = `${e.clientX - rect.left}px`;
        ripple.style.top = `${e.clientY - rect.top}px`;
        el.appendChild(ripple);
        const timeoutId = window.setTimeout(() => {
          ripple.remove();
          rippleTimeoutIds.delete(timeoutId);
        }, RIPPLE_DURATION_MS);
        rippleTimeoutIds.add(timeoutId);
      });
    });
  };
  window.addEventListener(
    'beforeunload',
    () => {
      rippleTimeoutIds.forEach((id) => window.clearTimeout(id));
      rippleTimeoutIds.clear();
    },
    { once: true }
  );

  const uploadZone = document.querySelector('.upload-zone');
  if (uploadZone) {
    const input = uploadZone.querySelector('input[type="file"]');
    ['dragenter', 'dragover'].forEach((evt) =>
      uploadZone.addEventListener(evt, (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
      })
    );
    ['dragleave', 'drop'].forEach((evt) =>
      uploadZone.addEventListener(evt, (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
      })
    );
    uploadZone.addEventListener('drop', (e) => {
      const droppedFiles = e.dataTransfer && e.dataTransfer.files ? e.dataTransfer.files : null;
      if (!input || !droppedFiles || !droppedFiles.length) return;
      input.files = droppedFiles;
      input.dispatchEvent(new Event('change', { bubbles: true }));
    });
    if (input) {
      input.addEventListener('change', () => {
        const label = document.querySelector('.upload-file-label');
        if (label) label.textContent = input.files && input.files[0] ? input.files[0].name : '';
      });
    }
  }

  const newGoalBtn = document.querySelector('.new-goal-btn');
  const goalForm = document.querySelector('.goal-form-panel');
  const goalModalOverlay = document.querySelector('.goal-modal-overlay');
  const cancelGoalButtons = document.querySelectorAll('.cancel-goal-btn');
  const addGoalLink = document.querySelector('.add-goal-link');
  if (newGoalBtn && goalForm) {
    const trapGoalModalFocus = (e) => {
      if (e.key !== 'Tab' || !goalForm.classList.contains('is-open')) return;
      const focusableSelectors =
        'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';
      const focusableElements = Array.from(goalForm.querySelectorAll(focusableSelectors)).filter(
        (el) => el.offsetParent !== null
      );
      if (!focusableElements.length) return;
      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];
      if (e.shiftKey && document.activeElement === firstElement) {
        e.preventDefault();
        lastElement.focus();
      } else if (!e.shiftKey && document.activeElement === lastElement) {
        e.preventDefault();
        firstElement.focus();
      }
    };
    const handleGoalModalKeydown = (e) => {
      if (e.key === 'Escape' && goalForm.classList.contains('is-open')) hideGoalForm();
      trapGoalModalFocus(e);
    };
    const showGoalForm = () => {
      goalForm.classList.add('is-open');
      goalForm.setAttribute('aria-hidden', 'false');
      goalModalOverlay?.classList.add('is-open');
      goalModalOverlay?.setAttribute('aria-hidden', 'false');
      document.body.classList.add('modal-open');
      window.addEventListener('keydown', handleGoalModalKeydown);
      const initialGoalInput = goalForm.querySelector('#goal-title');
      initialGoalInput?.focus();
    };
    const hideGoalForm = () => {
      goalForm.classList.remove('is-open');
      goalForm.setAttribute('aria-hidden', 'true');
      goalModalOverlay?.classList.remove('is-open');
      goalModalOverlay?.setAttribute('aria-hidden', 'true');
      document.body.classList.remove('modal-open');
      window.removeEventListener('keydown', handleGoalModalKeydown);
    };
    newGoalBtn.addEventListener('click', showGoalForm);
    addGoalLink?.addEventListener('click', showGoalForm);
    cancelGoalButtons.forEach((button) => button.addEventListener('click', hideGoalForm));
    goalModalOverlay?.addEventListener('click', hideGoalForm);
  }

  const profileFileInput = document.querySelector('.profile-file-input');
  const uploadArea = document.querySelector('.upload-area');
  const fileLabel = document.querySelector('.file-label');
  if (profileFileInput && uploadArea && fileLabel) {
    uploadArea.addEventListener('click', () => profileFileInput.click());
    uploadArea.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        profileFileInput.click();
      }
    });
    profileFileInput.addEventListener('change', (e) => {
      const target = e.target;
      if (!target) return;
      if (target.files && target.files[0]) {
        fileLabel.textContent = target.files[0].name;
        fileLabel.classList.add('file-selected');
        return;
      }
      fileLabel.textContent = 'No file selected';
      fileLabel.classList.remove('file-selected');
    });
  }

  const initCountUp = () => {
    const animateStat = (el) => {
      const target = parseFloat(el.dataset.target || el.dataset.count);
      if (Number.isNaN(target)) return;
      const unit = el.dataset.unit || '';
      if (prefersReducedMotion) {
        el.textContent = `${Math.round(target)}${unit}`;
        return;
      }

      if (typeof ScrollTrigger !== 'undefined' && typeof gsap !== 'undefined') {
        ScrollTrigger.create({
          trigger: el,
          start: 'top 85%',
          once: true,
          onEnter: () => {
            gsap.fromTo({ val: 0 }, { val: 0 }, {
              val: target,
              duration: 1.8,
              ease: 'power2.out',
              onUpdate() {
                const value = Math.round(this.targets()[0].val);
                el.textContent = `${value}${unit}`;
              },
            });
          },
        });
        return;
      }

      const duration = 1800;
      let started = false;
      const trigger = () => {
        if (started) return;
        started = true;
        const startTime = performance.now();
        const frame = (now) => {
          const p = Math.min((now - startTime) / duration, 1);
          el.textContent = `${Math.round(target * p)}${unit}`;
          if (p < 1) requestAnimationFrame(frame);
        };
        requestAnimationFrame(frame);
      };
      if ('IntersectionObserver' in window) {
        const observer = new IntersectionObserver((entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              trigger();
              observer.disconnect();
            }
          });
        }, { threshold: 0.25 });
        observer.observe(el);
      } else {
        trigger();
      }
    };

    document.querySelectorAll('.count-up, .stat-number').forEach(animateStat);
  };

  const markHighProgressBars = () => {
    document.querySelectorAll('.bar span, .mini-bars span, .bench-bar span').forEach((el) => {
      const width = parseFloat((el.style.width || '').replace('%', ''));
      if (!Number.isNaN(width) && width >= 80) el.classList.add('high-progress');
    });
  };

  const initGSAP = () => {
    if (typeof gsap === 'undefined' || typeof ScrollTrigger === 'undefined') return;
    if (prefersReducedMotion) {
      document.querySelectorAll('.animate-in').forEach((el) => {
        el.style.opacity = '1';
        el.style.transform = 'none';
      });
      return;
    }
    gsap.registerPlugin(ScrollTrigger);
    // Gentle multi-direction drift values for decorative hero glow shapes.
    const heroShapeMotions = [
      { selector: '.hero-shape-one', x: 26, y: -18, duration: 8.5 },
      { selector: '.hero-shape-two', x: -24, y: 22, duration: 10 },
      { selector: '.hero-shape-three', x: 20, y: -14, duration: 9 },
    ];

    gsap.fromTo(
      '.hero-glow',
      { opacity: 0.26, scale: 0.95 },
      { opacity: 0.58, scale: 1.08, duration: 5, ease: 'sine.inOut', yoyo: true, repeat: -1 }
    );

    heroShapeMotions.forEach(({ selector, x, y, duration }) => {
      gsap.to(selector, { x, y, duration, ease: 'sine.inOut', yoyo: true, repeat: -1 });
    });

    gsap.fromTo(
      '.hero-content .section-label, .hero-content h1, .hero-content p, .hero-actions, .hero-proof',
      { opacity: 0, y: 28 },
      { opacity: 1, y: 0, duration: 0.9, ease: 'power2.out', stagger: 0.14, delay: 0.18 }
    );

    gsap.utils.toArray('.animate-in').forEach((el) => {
      gsap.fromTo(
        el,
        { opacity: 0, y: 40 },
        {
          opacity: 1,
          y: 0,
          duration: 0.8,
          ease: 'power2.out',
          scrollTrigger: { trigger: el, start: 'top 88%' },
        }
      );
    });

    gsap.utils.toArray('.stagger-children').forEach((container) => {
      const children = Array.from(container.children);
      if (!children.length) return;
      gsap.fromTo(
        children,
        { opacity: 0, y: 24 },
        {
          opacity: 1,
          y: 0,
          duration: 0.6,
          ease: 'power2.out',
          stagger: 0.09,
          scrollTrigger: { trigger: container, start: 'top 82%' },
        }
      );
    });

    gsap.fromTo(
      '.how-steps .how-step',
      { opacity: 0, x: -26 },
      {
        opacity: 1,
        x: 0,
        duration: 0.72,
        stagger: 0.16,
        ease: 'power2.out',
        scrollTrigger: { trigger: '.how-steps', start: 'top 82%' },
      }
    );

    gsap.fromTo(
      '.problem-stats > .problem-stat-card',
      { opacity: 0, y: 22 },
      {
        opacity: 1,
        y: 0,
        duration: 0.6,
        stagger: 0.12,
        ease: 'power2.out',
        scrollTrigger: { trigger: '.problem-stats', start: 'top 84%' },
      }
    );

    gsap.fromTo(
      '.modules-grid .module-cell',
      { opacity: 0, y: 28 },
      {
        opacity: 1,
        y: 0,
        duration: 0.58,
        stagger: 0.05,
        ease: 'power2.out',
        scrollTrigger: { trigger: '.modules-grid', start: 'top 85%' },
      }
    );

    gsap.to('.step-icon', {
      y: -4,
      duration: 1.8,
      ease: 'sine.inOut',
      stagger: 0.12,
      yoyo: true,
      repeat: -1,
    });
  };

  /* ==========================================================================
     ✅ Real-time Notifications (Django Channels / WebSockets)
     - Requires base.html to set: window.__NOTIF__ = { isAuthenticated, wsPath, notificationsUrl, unreadCount }
     - Requires base.html to include:
       - <span id="notif-unread-badge">...</span>
       - <div id="notif-toast-container"></div>
     ========================================================================== */

  const initRealtimeNotifications = () => {
    const cfg = window.__NOTIF__ || {};
    if (!cfg.isAuthenticated) return;

    const badgeEl = document.getElementById('notif-unread-badge');
    const toastContainer = document.getElementById('notif-toast-container');

    const setBadge = (count) => {
      if (!badgeEl) return;
      const n = Number(count || 0);
      badgeEl.textContent = String(n);
      badgeEl.style.display = n > 0 ? 'inline-block' : 'none';
    };

    const escapeHtml = (s) =>
      String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

    const showToast = (title, message, url) => {
      if (!toastContainer) return;

      const el = document.createElement('div');
      el.style.cssText =
        'width:320px;background:#111827;color:#fff;border:1px solid rgba(255,255,255,.12);' +
        'border-radius:12px;padding:12px;box-shadow:0 10px 25px rgba(0,0,0,.25);';

      const safeTitle = escapeHtml(title || 'Notification');
      const safeMsg = escapeHtml(message || '');
      const safeUrl = url ? String(url) : '';

      el.innerHTML = `
        <div style="display:flex;justify-content:space-between;gap:10px;">
          <div style="font-weight:700;font-size:14px;">${safeTitle}</div>
          <button type="button" aria-label="Close"
            style="background:transparent;border:none;color:#9CA3AF;cursor:pointer;font-size:16px;line-height:16px;">×</button>
        </div>
        <div style="margin-top:6px;color:#D1D5DB;font-size:13px;">${safeMsg}</div>
        ${safeUrl ? `<a href="${safeUrl}" style="display:inline-block;margin-top:8px;color:#60A5FA;font-size:13px;text-decoration:underline;">View</a>` : ''}
      `;

      el.querySelector('button').addEventListener('click', () => el.remove());
      toastContainer.appendChild(el);

      window.setTimeout(() => {
        if (el && el.parentNode) el.remove();
      }, 6000);
    };

    // initial badge from server render
    setBadge(cfg.unreadCount);

    let socket = null;
    let retryMs = 1000;

    const connect = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const path = cfg.wsPath || '/ws/notifications/';
      const wsUrl = `${protocol}://${window.location.host}${path}`;

      socket = new WebSocket(wsUrl);

      socket.onopen = () => {
        retryMs = 1000;
        // ask for unread count (consumer supports it)
        try {
          socket.send(JSON.stringify({ action: 'get_unread_count' }));
        } catch (e) {
          // ignore
        }
      };

      socket.onmessage = (event) => {
        let data;
        try {
          data = JSON.parse(event.data);
        } catch (e) {
          return;
        }

        if (data.type === 'unread_count') {
          setBadge(data.unread);
          return;
        }

        if (data.type === 'notification') {
          const current = badgeEl ? Number(badgeEl.textContent || 0) : 0;
          setBadge(current + 1);

          showToast(
            data.title,
            data.message,
            data.related_url || cfg.notificationsUrl || '/notifications/'
          );
        }
      };

      socket.onclose = () => {
        window.setTimeout(connect, retryMs);
        retryMs = Math.min(retryMs * 2, 15000);
      };

      socket.onerror = () => {
        try {
          socket.close();
        } catch (e) {
          // ignore
        }
      };
    };

    connect();
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      markHighProgressBars();
      initGSAP();
      initCountUp();
      initRipples();
      initRealtimeNotifications(); // ✅ added
    });
  } else {
    markHighProgressBars();
    initGSAP();
    initCountUp();
    initRipples();
    initRealtimeNotifications(); // ✅ added
  }
})();