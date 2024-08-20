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
	"errors"
	"fmt"
	"math"
	"strings"
)

func selectNode(nodes []Node, podName string) (Node, error) {

	nodeData := getNodeData()

	var nodeIdx = -1
	var bestWatts int64 = math.MaxInt64

	nodeIpMap := getIpToNodeMap()

	fmt.Printf("nodeData has %d nodes (Scaphandre) and k8s has %d nodes", len(nodeData), len(nodes))
	fmt.Printf("Scaphandre data: %v\n\n", nodeData)

	nodeCorr, err := getNodeCorrections()
	if err != nil {
		return Node{}, fmt.Errorf("Failed to comput NodeCorrections: %v\n", err)
	}
	// run over available nodes
	for idx, node := range nodes {

		if strings.Contains(node.Metadata.Name, "controller") {
			continue
		}

		// and find the matching Scaphandre data
		for _, nd := range nodeData {
			nodeName, ok := nodeIpMap[nd.nodeIP]
			if !ok {
				fmt.Printf(" Could not find the  NodeName  fo IP = %s\n", nd.nodeIP)
			} else {
				fmt.Printf("Mapped IP ' %s' to NodeName %s\n", nd.nodeIP, nodeName)
			}
			if node.Metadata.Name == nodeName {
				fmt.Printf("Checking node %s with Watts %d", node.Metadata.Name, nd.nodeWatts)

				extraEnergy := 0
				for _, nc := range nodeCorr {
					if nc.NodeName == nodeName {
						extraEnergy = int(nc.ExtraEnergy)
						fmt.Printf("For node '%s'  found correction  %d\n", nodeName, extraEnergy)
						break
					}
				}
				correctedNodeWatts := nd.nodeWatts + int64(extraEnergy)
				if correctedNodeWatts <= bestWatts {
					nodeIdx = idx
					bestWatts = nd.nodeWatts
					fmt.Printf(" selected node %d with Watts %d", nodeIdx, bestWatts)
				}
				break // break from the inner loop as we found the matching node

			}

		}
	}

	fmt.Printf("\nSelectNode:  Schedule pod at node %d  out of %d nodes\n", nodeIdx, len(nodes))

	if nodeIdx < 0 {
		return Node{}, errors.New("No node found")
	}
	return nodes[nodeIdx], nil
}
