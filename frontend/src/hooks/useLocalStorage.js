// import { useState, useEffect } from 'react';

// // ==============================|| LOCAL STORAGE ||============================== //

// export default function useLocalStorage(key, defaultValue) {
//   const [value, setValue] = useState(() => {
//     const storedValue = typeof window !== 'undefined' ? localStorage.getItem(key) : null;
//     return storedValue === null ? defaultValue : JSON.parse(storedValue);
//   });

//   useEffect(() => {
//     const listener = (e) => {
//       if (typeof window !== 'undefined' && e.storageArea === localStorage && e.key === key) {
//         setValue(e.newValue ? JSON.parse(e.newValue) : e.newValue);
//       }
//     };
//     window.addEventListener('storage', listener);

//     return () => {
//       window.removeEventListener('storage', listener);
//     };
//   }, [key]);

//   const setValueInLocalStorage = (newValue) => {
//     setValue((currentValue) => {
//       const result = typeof newValue === 'function' ? newValue(currentValue) : newValue;
//       if (typeof window !== 'undefined') localStorage.setItem(key, JSON.stringify(result));
//       return result;
//     });
//   };

//   return [value, setValueInLocalStorage];
// }

// hooks/useLocalStorage.js
import { useState, useEffect } from 'react';

/**
 * Hook LocalStorage avec :
 * - lecture fiable au montage
 * - migration optionnelle depuis un prefix (ex: 'userTablePageSize:')
 * - suppression des anciennes clés (sécurité)
 */
export default function useLocalStorage(key, defaultValue, options = {}) {
  const { migrateFromPrefix = null } = options;

  // Initialisation "safe"
  const [value, setValue] = useState(() => {
    if (typeof window === 'undefined') return defaultValue;
    try {
      // Canonique d'abord
      const stored = window.localStorage.getItem(key);
      if (stored !== null) return JSON.parse(stored);

      // Migration lazy si nécessaire
      if (migrateFromPrefix) {
        const migrated = migrateOnce(key, migrateFromPrefix, defaultValue);
        return migrated;
      }

      return defaultValue;
    } catch {
      return defaultValue;
    }
  });

  // Relecture au montage dans l’onglet courant (pas d’event 'storage' ici)
  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      let next = window.localStorage.getItem(key);
      if (next !== null) {
        setValue(JSON.parse(next));
        return;
      }
      if (options.migrateFromPrefix) {
        const migrated = migrateOnce(key, options.migrateFromPrefix, defaultValue);
        setValue(migrated);
      }
    } catch {
      /* noop */
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  // Sync inter-onglets
  useEffect(() => {
    const onStorage = (e) => {
      if (e.storageArea === window.localStorage && e.key === key) {
        try {
          setValue(e.newValue !== null ? JSON.parse(e.newValue) : defaultValue);
        } catch {
          setValue(defaultValue);
        }
      }
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, [key, defaultValue]);

  const setValueInLocalStorage = (updater) => {
    setValue((prev) => {
      const next = typeof updater === 'function' ? updater(prev) : updater;
      try {
        const current = window.localStorage.getItem(key);
        const currentParsed = current !== null ? JSON.parse(current) : undefined;
        // éviter les écritures inutiles
        if (JSON.stringify(currentParsed) !== JSON.stringify(next)) {
          window.localStorage.setItem(key, JSON.stringify(next));
        }
      } catch {
        /* noop */
      }
      return next;
    });
  };

  return [value, setValueInLocalStorage];
}
