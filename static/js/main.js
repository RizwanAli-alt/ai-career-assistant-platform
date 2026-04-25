(function () {
  'use strict';

  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const navbar = document.querySelector('.navbar');
  const hamburger = document.querySelector('.hamburger');
  const mobileMenu = document.querySelector('.mobile-menu');
  const mobileClose = document.querySelector('.mobile-menu-close');
  const NAV_OPACITY_MIN = 0.72;
  const NAV_OPACITY_MAX = 0.96;
  const NAV_OPACITY_SCROLL_RANGE = 420;
  const RIPPLE_DURATION_MS = 600;
  const rippleTimeoutIds = new Set();

  const setNavbarState = () => {
    if (!navbar) return;
    const scrolled = window.scrollY > 40;
    navbar.classList.toggle('scrolled', scrolled);
    const dynamicOpacity = Math.min(NAV_OPACITY_MAX,
      NAV_OPACITY_MIN + (window.scrollY / NAV_OPACITY_SCROLL_RANGE) * (NAV_OPACITY_MAX - NAV_OPACITY_MIN));
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
  window.addEventListener('scroll', () => {
    if (navTicking) return;
    navTicking = true;
    window.requestAnimationFrame(() => {
      setNavbarState();
      navTicking = false;
    });
  }, { passive: true });

  if (hamburger && mobileMenu) {
    hamburger.addEventListener('click', () => {
      const isOpen = mobileMenu.classList.contains('open');
      if (isOpen) closeMenu(); else openMenu();
    });
    mobileMenu.querySelectorAll('a').forEach((a) => a.addEventListener('click', closeMenu));
    if (mobileClose) mobileClose.addEventListener('click', closeMenu);
    window.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeMenu(); });
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
  window.addEventListener('beforeunload', () => {
    rippleTimeoutIds.forEach((id) => window.clearTimeout(id));
    rippleTimeoutIds.clear();
  }, { once: true });

  const uploadZone = document.querySelector('.upload-zone');
  if (uploadZone) {
    const input = uploadZone.querySelector('input[type="file"]');
    ['dragenter', 'dragover'].forEach((evt) => uploadZone.addEventListener(evt, (e) => {
      e.preventDefault();
      uploadZone.classList.add('dragover');
    }));
    ['dragleave', 'drop'].forEach((evt) => uploadZone.addEventListener(evt, (e) => {
      e.preventDefault();
      uploadZone.classList.remove('dragover');
    }));
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
      const focusableSelectors = 'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';
      const focusableElements = Array.from(goalForm.querySelectorAll(focusableSelectors))
        .filter((el) => el.offsetParent !== null);
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
            gsap.fromTo({ val: 0 }, { val: 0 }, { val: target, duration: 1.8, ease: 'power2.out', onUpdate() {
              const value = Math.round(this.targets()[0].val);
              el.textContent = `${value}${unit}`;
            } });
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

    gsap.fromTo('.hero-glow',
      { opacity: 0.26, scale: 0.95 },
      { opacity: 0.58, scale: 1.08, duration: 5, ease: 'sine.inOut', yoyo: true, repeat: -1 });

    heroShapeMotions.forEach(({ selector, x, y, duration }) => {
      gsap.to(selector, { x, y, duration, ease: 'sine.inOut', yoyo: true, repeat: -1 });
    });

    gsap.fromTo('.hero-content .section-label, .hero-content h1, .hero-content p, .hero-actions, .hero-proof',
      { opacity: 0, y: 28 },
      { opacity: 1, y: 0, duration: 0.9, ease: 'power2.out', stagger: 0.14, delay: 0.18 });

    gsap.utils.toArray('.animate-in').forEach((el) => {
      gsap.fromTo(el,
        { opacity: 0, y: 40 },
        { opacity: 1, y: 0, duration: 0.8, ease: 'power2.out', scrollTrigger: { trigger: el, start: 'top 88%' } });
    });

    gsap.utils.toArray('.stagger-children').forEach((container) => {
      const children = Array.from(container.children);
      if (!children.length) return;
      gsap.fromTo(children,
        { opacity: 0, y: 24 },
        { opacity: 1, y: 0, duration: 0.6, ease: 'power2.out', stagger: 0.09, scrollTrigger: { trigger: container, start: 'top 82%' } });
    });

    gsap.fromTo('.how-steps .how-step',
      { opacity: 0, x: -26 },
      { opacity: 1, x: 0, duration: 0.72, stagger: 0.16, ease: 'power2.out', scrollTrigger: { trigger: '.how-steps', start: 'top 82%' } });

    gsap.fromTo('.problem-stats > .problem-stat-card',
      { opacity: 0, y: 22 },
      { opacity: 1, y: 0, duration: 0.6, stagger: 0.12, ease: 'power2.out', scrollTrigger: { trigger: '.problem-stats', start: 'top 84%' } });

    gsap.fromTo('.modules-grid .module-cell',
      { opacity: 0, y: 28 },
      { opacity: 1, y: 0, duration: 0.58, stagger: 0.05, ease: 'power2.out', scrollTrigger: { trigger: '.modules-grid', start: 'top 85%' } });

    gsap.to('.step-icon',
      { y: -4, duration: 1.8, ease: 'sine.inOut', stagger: 0.12, yoyo: true, repeat: -1 });

  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      markHighProgressBars();
      initGSAP();
      initCountUp();
      initRipples();
    });
  } else {
    markHighProgressBars();
    initGSAP();
    initCountUp();
    initRipples();
  }
})();
