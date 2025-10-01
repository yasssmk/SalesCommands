// frontend/src/utils/monitoring.js

/**
 * Monitoring Module - MVP
 * 
 * Collecteur centralisé de métriques pour le frontend
 * Stockage en mémoire avec export périodique en console
 * 
 * ✅ UPDATED: Integrated PII sanitization for all logs
 * 
 * @module utils/monitoring
 */

// 🔒 SECURITY: Import sanitization utilities
import { safeConsole, sanitizeObject } from './logSanitizer';

// ==============================|| METRICS STORE ||============================== //

class MetricsCollector {
  constructor() {
    // Store pour les latences par endpoint
    this.endpointMetrics = new Map();
    
    // Configuration
    this.config = {
      maxHistorySize: 100,        // Garder les 100 dernières mesures par endpoint
      enableConsoleLog: true,      // Log en console en dev
      logInterval: 60000,          // Log summary toutes les minutes en dev
      percentiles: [50, 90, 95, 99] // Percentiles à calculer
    };
    
    // Démarrer le reporting périodique en dev
    if (process.env.NODE_ENV === 'development' && this.config.enableConsoleLog) {
      this.startPeriodicReporting();
    }
  }

  // ==============================|| RECORD METRIC ||============================== //
  
  /**
   * Enregistre une latence pour un endpoint
   * @param {string} endpoint - URL de l'endpoint
   * @param {number} duration - Durée en ms
   * @param {Object} metadata - Métadonnées additionnelles
   */
  recordEndpointLatency(endpoint, duration, metadata = {}) {
    // Nettoyer l'endpoint (enlever query params pour grouper)
    const cleanEndpoint = this.cleanEndpoint(endpoint);
    
    // Initialiser si nécessaire
    if (!this.endpointMetrics.has(cleanEndpoint)) {
      this.endpointMetrics.set(cleanEndpoint, {
        endpoint: cleanEndpoint,
        measurements: [],
        errors: 0,
        successes: 0,
        lastUpdated: null
      });
    }
    
    const metrics = this.endpointMetrics.get(cleanEndpoint);
    
    // Ajouter la mesure
    metrics.measurements.push({
      duration,
      timestamp: Date.now(),
      success: metadata.success !== false,
      statusCode: metadata.statusCode,
      cached: metadata.cached || false
    });
    
    // Compter succès/erreurs
    if (metadata.success !== false) {
      metrics.successes++;
    } else {
      metrics.errors++;
    }
    
    metrics.lastUpdated = Date.now();
    
    // Limiter la taille de l'historique
    if (metrics.measurements.length > this.config.maxHistorySize) {
      metrics.measurements.shift();
    }
    
    // 🔒 UPDATED: Log immédiat en dev pour les requêtes lentes (with sanitization)
    if (process.env.NODE_ENV === 'development' && duration > 1000) {
      safeConsole.warn(`⚠️ [Slow Request] ${cleanEndpoint}: ${duration.toFixed(0)}ms`);
    }
  }
  
  /**
   * Enregistre une erreur pour un endpoint
   * @param {string} endpoint - URL de l'endpoint
   * @param {Error} error - Erreur capturée
   * @param {Object} metadata - Métadonnées additionnelles
   */
  recordEndpointError(endpoint, error, metadata = {}) {
    const cleanEndpoint = this.cleanEndpoint(endpoint);
    
    this.recordEndpointLatency(endpoint, metadata.duration || 0, {
      success: false,
      statusCode: error.response?.status || 0,
      errorMessage: error.message,
      ...metadata
    });
    
    // 🔒 UPDATED: Log spécifique pour les erreurs en dev (with sanitization)
    if (process.env.NODE_ENV === 'development') {
      // Sanitize error object before logging
      const sanitizedErrorData = sanitizeObject({
        status: error.response?.status,
        message: error.message,
        duration: metadata.duration,
        // Remove sensitive data from response
        data: error.response?.data
      });
      
      safeConsole.error(`❌ [API Error] ${cleanEndpoint}:`, sanitizedErrorData);
    }
  }

  // ==============================|| ANALYTICS ||============================== //
  
  /**
   * Calcule les statistiques pour un endpoint
   * @param {string} endpoint - URL de l'endpoint
   * @returns {Object} Statistiques calculées
   */
  getEndpointStats(endpoint) {
    const cleanEndpoint = this.cleanEndpoint(endpoint);
    const metrics = this.endpointMetrics.get(cleanEndpoint);
    
    if (!metrics || metrics.measurements.length === 0) {
      return null;
    }
    
    const durations = metrics.measurements
      .filter(m => m.success)
      .map(m => m.duration)
      .sort((a, b) => a - b);
    
    if (durations.length === 0) {
      return {
        endpoint: cleanEndpoint,
        count: 0,
        errorRate: 1,
        stats: null
      };
    }
    
    return {
      endpoint: cleanEndpoint,
      count: metrics.measurements.length,
      successes: metrics.successes,
      errors: metrics.errors,
      errorRate: metrics.errors / metrics.measurements.length,
      stats: {
        min: Math.min(...durations),
        max: Math.max(...durations),
        avg: durations.reduce((a, b) => a + b, 0) / durations.length,
        p50: this.percentile(durations, 50),
        p90: this.percentile(durations, 90),
        p95: this.percentile(durations, 95),
        p99: this.percentile(durations, 99)
      },
      lastUpdated: metrics.lastUpdated
    };
  }
  
  /**
   * Obtient un résumé global de toutes les métriques
   * @returns {Object} Résumé global
   */
  getSummary() {
    const endpoints = Array.from(this.endpointMetrics.keys());
    const stats = endpoints.map(ep => this.getEndpointStats(ep)).filter(Boolean);
    
    if (stats.length === 0) {
      return { message: 'No metrics collected yet' };
    }
    
    // Trier par nombre d'appels (plus utilisés en premier)
    stats.sort((a, b) => b.count - a.count);
    
    // Calculer les métriques globales
    const totalCalls = stats.reduce((sum, s) => sum + s.count, 0);
    const totalErrors = stats.reduce((sum, s) => sum + s.errors, 0);
    const avgLatencies = stats.map(s => s.stats?.avg || 0).filter(v => v > 0);
    
    return {
      summary: {
        totalEndpoints: stats.length,
        totalCalls,
        totalErrors,
        globalErrorRate: totalErrors / totalCalls,
        globalAvgLatency: avgLatencies.length > 0 
          ? avgLatencies.reduce((a, b) => a + b, 0) / avgLatencies.length 
          : 0
      },
      topEndpoints: stats.slice(0, 5),
      slowestEndpoints: [...stats]
        .filter(s => s.stats)
        .sort((a, b) => b.stats.p95 - a.stats.p95)
        .slice(0, 5)
    };
  }

  // ==============================|| UTILITIES ||============================== //
  
  /**
   * Nettoie l'URL pour regrouper les métriques
   * @param {string} endpoint - URL complète
   * @returns {string} URL nettoyée
   */
  cleanEndpoint(endpoint) {
    if (!endpoint) return 'unknown';
    
    try {
        // Enlever la base URL si présente
        let clean = endpoint.replace(/^https?:\/\/[^\/]+/, '');
        
        // Enlever les query parameters
        clean = clean.split('?')[0];
        
        // IMPORTANT: Remplacer les UUIDs AVANT les IDs numériques
        // Pattern UUID complet : 8-4-4-4-12 caractères hex
        clean = clean.replace(
        /[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}/gi, 
        '{uuid}'
        );
        
        // Remplacer les IDs numériques par {id}
        // Seulement les nombres isolés entre slashes
        clean = clean.replace(/\/\d+\//g, '/{id}/');
        clean = clean.replace(/\/\d+$/g, '/{id}');
        
        return clean || endpoint;
    } catch (e) {
        return endpoint;
    }
  }
    
  /**
   * Calcule un percentile
   * @param {number[]} sortedArray - Tableau trié
   * @param {number} p - Percentile (0-100)
   * @returns {number} Valeur du percentile
   */
  percentile(sortedArray, p) {
    if (sortedArray.length === 0) return 0;
    const index = Math.ceil((p / 100) * sortedArray.length) - 1;
    return sortedArray[Math.max(0, index)];
  }
  
  /**
   * Formatage pour l'affichage
   * @param {number} ms - Millisecondes
   * @returns {string} Durée formatée
   */
  formatDuration(ms) {
    if (ms < 1000) return `${ms.toFixed(0)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  }
  
  /**
   * Démarre le reporting périodique en console
   * 🔒 UPDATED: All console output now sanitized
   */
  startPeriodicReporting() {
    setInterval(() => {
      const summary = this.getSummary();
      
      if (summary.summary) {
        // Style du header
        console.log(
          '%c📊 API Performance Report',
          'color: #0066cc; font-size: 14px; font-weight: bold; padding: 4px 0'
        );
        
        // Tableau de résumé avec couleurs
        const errorRateColor = summary.summary.globalErrorRate > 0.05 ? '#ff4444' : 
                              summary.summary.globalErrorRate > 0.01 ? '#ff9900' : '#00cc00';
        const avgLatencyColor = summary.summary.globalAvgLatency > 500 ? '#ff4444' :
                               summary.summary.globalAvgLatency > 200 ? '#ff9900' : '#00cc00';
        
        console.log(
          `  Total requests: %c${summary.summary.totalCalls}%c | Errors: %c${summary.summary.totalErrors}%c (${(summary.summary.globalErrorRate * 100).toFixed(2)}%) | Avg latency: %c${summary.summary.globalAvgLatency.toFixed(0)}ms`,
          'color: #0066cc; font-weight: bold',
          'color: inherit',
          `color: ${errorRateColor}; font-weight: bold`,
          'color: inherit',
          `color: ${avgLatencyColor}; font-weight: bold`
        );
        
        console.log('%c━━━━━━━━━━━━━━━━━━━━━━━━━━━━', 'color: #666');
        
        // Top endpoints (plus utilisés)
        if (summary.topEndpoints.length > 0) {
          console.log('%c📈 Most Used Endpoints:', 'color: #666; font-weight: bold');
          summary.topEndpoints.forEach((e, i) => {
            const badge = i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : '  ';
            console.log(
              `  ${badge} %c${e.endpoint}%c → ${e.count} calls, error rate: %c${(e.errorRate * 100).toFixed(1)}%`,
              'color: #666; font-family: monospace',
              'color: inherit',
              e.errorRate > 0.05 ? 'color: #ff4444; font-weight: bold' : 'color: #00cc00'
            );
          });
        }
        
        console.log('%c━━━━━━━━━━━━━━━━━━━━━━━━━━━━', 'color: #666');
        
        // Slowest endpoints
        if (summary.slowestEndpoints.length > 0) {
          console.log('%c🐌 Slowest Endpoints (P95):', 'color: #666; font-weight: bold');
          summary.slowestEndpoints.forEach((e, i) => {
            const badge = e.stats.p95 > 2000 ? '🔥' : e.stats.p95 > 1000 ? '🐌' : '⚠️';
            console.log(
              `  ${badge} %c${e.endpoint}%c → P95: %c${e.stats.p95.toFixed(0)}ms%c, Max: %c${e.stats.max.toFixed(0)}ms`,
              'color: #666; font-family: monospace',
              'color: inherit',
              'color: #ff4444; font-weight: bold',
              'color: inherit',
              'color: #ff0000; font-weight: bold'
            );
          });
        }
      }
      
      console.log('%c━━━━━━━━━━━━━━━━━━━━━━━━━━━━', 'color: #666');
      console.log(
        '%c💡 Tip: window.__metricsCollector for detailed analysis',
        'color: #666; font-style: italic; font-size: 11px'
      );
    }, this.config.logInterval);
  }
  
  /**
   * Reset toutes les métriques
   * 🔒 UPDATED: Sanitized console output
   */
  reset() {
    this.endpointMetrics.clear();
    safeConsole.log('🔄 Metrics collector reset');
  }
  
  /**
   * Export des métriques pour analyse externe
   * 🔒 UPDATED: Sanitized console output and data export
   * @returns {Object} Données exportables
   */
  export() {
    const data = {
      timestamp: new Date().toISOString(),
      metrics: Array.from(this.endpointMetrics.entries()).map(([key, value]) => ({
        endpoint: key,
        ...value
      })),
      summary: this.getSummary()
    };
    
    // En dev, permettre l'export via console (sanitized)
    if (process.env.NODE_ENV === 'development') {
      safeConsole.log('📤 Exporting metrics data:');
      // Sanitize data before stringifying (in case there's PII in error messages)
      const sanitizedData = sanitizeObject(data);
      console.log(JSON.stringify(sanitizedData, null, 2));
    }
    
    return data;
  }
}

// ==============================|| SINGLETON INSTANCE ||============================== //

const metricsCollector = new MetricsCollector();

// En dev, exposer globalement pour debug
if (process.env.NODE_ENV === 'development' && typeof window !== 'undefined') {
  window.__metricsCollector = metricsCollector;
  safeConsole.log('💡 Metrics collector available at window.__metricsCollector');
}

// ==============================|| EXPORTS ||============================== //

export default metricsCollector;

// Export des méthodes principales pour usage direct
export const {
  recordEndpointLatency,
  recordEndpointError,
  getEndpointStats,
  getSummary,
  reset,
  export: exportMetrics
} = metricsCollector;

// Export pour les hooks
export const useMetrics = () => metricsCollector;