package main

import (
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"strings"
)

// architectureProxy serves the live architecture and resilience console under
// /architecture on the same port as the shop. Requests are forwarded to the
// in-cluster architecture-service. It wraps the whole router so that the
// console's frequent polling does not appear in the shop's request logs.
func architectureProxy(next http.Handler) http.Handler {
	addr := os.Getenv("ARCHITECTURE_SERVICE_ADDR")
	if addr == "" {
		addr = "http://architecture-service:8090"
	}
	target, err := url.Parse(addr)
	if err != nil {
		return next
	}
	prefix := baseUrl + "/architecture"
	proxy := httputil.NewSingleHostReverseProxy(target)
	proxy.FlushInterval = -1 // stream server-sent events (live logs) immediately
	proxy.ErrorHandler = func(w http.ResponseWriter, _ *http.Request, _ error) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadGateway)
		_, _ = w.Write([]byte(`{"error":"architecture-service unavailable"}`))
	}
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == prefix {
			http.Redirect(w, r, prefix+"/", http.StatusMovedPermanently)
			return
		}
		if strings.HasPrefix(r.URL.Path, prefix+"/") {
			r.URL.Path = strings.TrimPrefix(r.URL.Path, prefix)
			r.URL.RawPath = ""
			proxy.ServeHTTP(w, r)
			return
		}
		next.ServeHTTP(w, r)
	})
}
