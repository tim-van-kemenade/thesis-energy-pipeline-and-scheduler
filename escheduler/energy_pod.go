// Copyright 2024 github.com/tim-van-kemenade
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package main

import (
	"fmt"
	"io/ioutil"
	"net/http"
	"os"
	"strconv"
)

func getPodMicroWatts() ([]byte, error) {
	requestURL := fmt.Sprintf("%s/api/v1/query?query=%s", prometheusHost, podWattQuery)
	resp, err := http.Get(requestURL)
	if err != nil {
		return nil, fmt.Errorf("Request '%s' Failed with error: %s\n", requestURL, err)
	}
	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("Request: '%s' returned status %d  ('%s')", requestURL, resp.StatusCode, resp.Status)
	}
	respBody, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("Request '%s' Failed to read response-body %v\n", requestURL, err)
	}
	return respBody, nil
}

type MicroWatts struct {
	PodName    string
	MicroWatts int64
	Count      int64
}

func NewMicroWatts(podName string, mw int64) *MicroWatts {
	return &MicroWatts{podName, mw, 1}
}

var microWatts = make(map[string]int64)
var avgPodMicroWatts = 0 // Average consumption over all current Pods

type PodLabels map[string]struct{}

var ScaphPodLabels PodLabels

var last_unix_t float64

// Detrmine the current set of PoddLabels that we see (PodName_<unique suffix>)
func setScaphPodLabels(podMetrics ScaphandreMetricContainer) {
	podLabels := make(PodLabels)

	for _, metricValue := range podMetrics.Data.Result {

		// build a set of PodLabels
		var podLabel = metricValue.Metric.Pod
		podLabels[podLabel] = struct{}{}
	}

	// store in a global variable. This is an atomic update and only one instance of this procedure exists, so no Mutex added.
	ScaphPodLabels = podLabels
}

// Update the Energy data of Pods by adding new pods, or computing an average of existing values and the new average.
// For a PodName (Job) that exists for some time this effectivelly means that the:
//   - Measurement T (current measurement) has a weight of %50
//   - Measurement T-1 has weight 25%
//   - Measurement T-2 has weight 12.5%
//   - ......
//     However, if multiple replicas of same Pod are observed in a single measurement we take the average microWatt consumption over these Pods.
func updatePodMicroWatts(podMetrics ScaphandreMetricContainer) {

	var avgMicroWatts []MicroWatts

	unix_t := 0.0

	totalMw := 0
	countPod := 0
	for idx, metricValue := range podMetrics.Data.Result {
		if idx == 0 {
			// all metrics have the same timestamp
			unix_t = metricValue.Value[0].(float64)
			if unix_t > last_unix_t {
				fmt.Printf("updatePodMicroWatts:  Time progressed from %f at last iteration to %f now\n", last_unix_t, unix_t)
				last_unix_t = unix_t
			} else {
				if unix_t == last_unix_t {
					fmt.Printf("updatePodMicroWatts: Error Time did not progresse (was %f  and now still %f)\n", last_unix_t, unix_t)
				} else {
					fmt.Printf("updatePodMicroWatts: ERROR Time moves backward (was %f  and now %f)\n", last_unix_t, unix_t)
				}
			}
		}

		var podName = metricValue.Metric.Job
		var metric = metricValue.Value[1].(string)
		var metricVal, err2 = strconv.ParseInt(metric, 10, 64)
		if err2 != nil {
			fmt.Printf("Failed to parse metric: %s. Error: %v", err2)
		}

		totalMw += int(metricVal)
		countPod += 1

		found := false
		for _, mw := range avgMicroWatts {
			if mw.PodName == podName {
				mw.Count += 1
				mw.MicroWatts += metricVal
				found = true
				break
			}
		}
		if !found {
			// append
			mw := NewMicroWatts(podName, metricVal)
			fmt.Printf("updatePodMicrowatts: Observed next Pod for the first time: %v\n", mw)
			avgMicroWatts = append(avgMicroWatts, *mw)
		}

	}

	// now append the averages to the long term storage
	for _, mw := range avgMicroWatts {

		metricVal := mw.MicroWatts / mw.Count // compute the average
		currVal, ok := microWatts[mw.PodName]
		if ok {
			// compute the average
			metricVal = (metricVal + currVal) / 2
		}
		fmt.Printf("updatePodMicroWatts: update for %s to value %d\n", mw.PodName, metricVal)
		microWatts[mw.PodName] = metricVal
	}

	// and update the average
	avgPodMicroWatts = totalMw / countPod

	fmt.Printf("Extracted data at time %d: Prometius last_unix_t = %d\n", getCurrentUnix(), last_unix_t)

}

func updatePoddata() error {

	bytes, err := getPodMicroWatts()

	if err != nil {
		return fmt.Errorf("Failed to run Prometeus-request: %v", err)
	}

	podMetrics, err1 := parseScaphandreMetric(bytes)
	if err1 != nil {
		return fmt.Errorf("Failed to parse response: %v", err1)
	}

	setScaphPodLabels(podMetrics)
	updatePodMicroWatts(podMetrics)

	return nil
}
