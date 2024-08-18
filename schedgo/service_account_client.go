package main

import (
	// "crypto/tls"
	"crypto/tls"
	"crypto/x509"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"os"
)

func listFiles(folder string) {
	entries, err := os.ReadDir(folder)
	if err != nil {
		log.Fatal(err)
	}

	fmt.Printf("Listing the files in folder: %s", folder)
	for idx, e := range entries {
		fmt.Printf("  %d: %s\n", idx+1, e.Name())
	}
}

func buildRestClient() (*http.Client, string) {
	caCert, err := ioutil.ReadFile("/var/run/secrets/kubernetes.io/serviceaccount/ca.crt")
	if err != nil {
		log.Fatal(err)
		panic(err)
	}
	token, err := ioutil.ReadFile("/var/run/secrets/kubernetes.io/serviceaccount/token")
	if err != nil {
		log.Fatal(err)
		panic(err)
	}
	caCertPool := x509.NewCertPool()
	caCertPool.AppendCertsFromPEM(caCert)

	client := &http.Client{
		Transport: &http.Transport{
			TLSClientConfig: &tls.Config{
				RootCAs: caCertPool,
			},
		},
	}
	// extract the http-client and thus ignore the advanced features of the RestClient (such as rate-limiting)
	bearer := "Bearer " + string(token)
	return client, bearer
}

// NOTE: Could add a mutex to prevent that the k8sClient is created multiple times. However, this is nog harmfull.
var cachedK8sClient *http.Client = nil
var cachedBearer string = ""

func getK8sClient() (*http.Client, string) {
	if cachedK8sClient == nil {
		client, bearerStr := buildRestClient()
		// store created value in the globals for reuse
		cachedK8sClient = client
		cachedBearer = bearerStr

	}
	return cachedK8sClient, cachedBearer
}

func executeRequest(request *http.Request) (*http.Response, error) {
	client, bearer := getK8sClient()
	request.Header.Set("Authorization", bearer)
	resp, err := client.Do(request)
	return resp, err
}
