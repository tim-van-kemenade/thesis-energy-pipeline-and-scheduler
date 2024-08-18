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
	"strconv"
	"strings"
	"sync"
	// to be removed
	// to be removed
	// to be removed
)

type NodeData struct {
	nodeIP    string
	nodePort  int32
	nodeWatts int64
	t         float64
}

type NodeDataContainer struct {
	mu          sync.Mutex
	nodeData    []NodeData
	last_unix_t float64
}

var ndContainer NodeDataContainer

// set Node data while ensuring the lock, annd also check if the provided data has a newer timestamp (Prometeus received a new Scaphandre sample)
func setNodeData(nodeData []NodeData, unix_t float64) bool {
	ndContainer.mu.Lock()
	defer ndContainer.mu.Unlock()
	ndContainer.nodeData = nodeData
	time_progressed := unix_t > ndContainer.last_unix_t
	if time_progressed {
		ndContainer.last_unix_t = unix_t
	} else {
		if unix_t < ndContainer.last_unix_t {
			fmt.Printf("ERROR: the time seems to run backward. Observed %d (epoch-time) and now time slipped back to %d", ndContainer.last_unix_t, unix_t)
		}
	}
	return time_progressed
}

// extract a copy of the NodeData, such we are sure the data is not mutated will using it.
func getNodeData() []NodeData {
	// make a copy of the nodeData to nd
	ndContainer.mu.Lock()
	nd := make([]NodeData, len(ndContainer.nodeData), len(ndContainer.nodeData))
	fmt.Printf("Container has #%d nodes", len(ndContainer.nodeData))
	num := copy(nd, ndContainer.nodeData)
	fmt.Printf("However, Copy has length %d   (copied %d items)", len(nd), num)
	ndContainer.mu.Unlock()
	return nd
}

// New methods for collecting Node-Energy

func getNodeMicroWatts() ([]byte, error) {
	requestURL := fmt.Sprintf("%s/api/v1/query?query=%s", prometheusHost, hostWattQuery)
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

func setNodeEnergy() (bool, error) {

	bytes, err := getNodeMicroWatts()

	if err != nil {
		return false, fmt.Errorf("Failed to run Prometeus-request: %v", err)
	}

	var nodeData []NodeData
	unix_t := 0.0

	nodeMetrics, err1 := parseScaphandreMetric(bytes)
	if err1 != nil {
		return false, fmt.Errorf("Failed to parse response: %v", err1)
	}

	for idx, metricValue := range nodeMetrics.Data.Result {
		if idx == 0 {
			// all metrics have the same timestamp
			unix_t = metricValue.Value[0].(float64)
		}
		instance := metricValue.Metric.Instance
		theIP, thePort := splitToIpPort(instance)

		var metric = metricValue.Value[1].(string)
		var mWatts, err2 = strconv.ParseInt(metric, 10, 64)
		if err2 != nil {
			return false, fmt.Errorf("Failed to parse metric: %s. Error: %v", err2)
		}

		nodeData = append(nodeData, NodeData{theIP, thePort, mWatts, unix_t})
	}

	fmt.Printf("Extracted node-energy data at time %d: Prometeus last_unix_t = %d\n", getCurrentUnix(), unix_t)

	time_progressed := setNodeData(nodeData, unix_t)

	return time_progressed, nil
}

// split an <ip>:<port> in its two parts, the IP (string) and the port (int32)
func splitToIpPort(instance string) (string, int32) {
	parts := strings.Split(instance, ":")
	theIP := parts[0]
	var thePort int32
	if len(parts) > 1 {
		tmp, err := strconv.ParseInt(parts[1], 10, 32)
		if err != nil {
			fmt.Printf("Could not parse port '%s' to an int32", parts[1])
		}
		thePort = int32(tmp) // could not directly assign to thePort as ParseInt returns an int64
	} else {
		thePort = -1
	}
	return theIP, thePort
}
