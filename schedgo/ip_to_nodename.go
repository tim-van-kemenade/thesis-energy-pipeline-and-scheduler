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
)

// a mapping from the IP-address, as used in Scaphandre, to the NodeName as used in Kubernetes
var cachedIpToNodeMap = make(map[string]string)

// build a mapping IPadresses to the corresponding node name
func buildIpToNodeMap() {
	podList, err := getPods()
	if err != nil {
		panic(fmt.Errorf("buildNodeMapIP failed. Error: %v\n", err))
	}

	for idx, pod := range podList.Items {
		podName := pod.Spec.NodeName
		podIp := pod.Status.PodIP

		fmt.Printf(" %d: mapping podNodeName = '%s' to podIP = '%s'\n", idx, podName, podIp)
		orgName, ok := cachedIpToNodeMap[podIp]
		if ok && orgName != podName {
			fmt.Printf("REMAPPING IP '%s'  from '%s' to new podName '%s'\n", podIp, orgName, podName)
		}
		cachedIpToNodeMap[podIp] = podName
	}
}

// Retrieve the cached nodeIPmap, and if not present build it from scratch
func getIpToNodeMap() map[string]string {
	if len(cachedIpToNodeMap) == 0 {
		buildIpToNodeMap()
	}
	return cachedIpToNodeMap
}
