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
	"time"
)

func getCurrentUnix() int64 {
	return time.Now().Unix()
}

type PendingPod struct {
	PodName  string
	NodeName string
	t_unix   int64
}

var pendingPods []PendingPod

const maxAgeSeconds = 14

func queueBindOperation(podName string, nodeName string) {
	t_unix := getCurrentUnix()
	var pod = PendingPod{podName, nodeName, t_unix}

	fmt.Printf("queueBindOperation: queing %v\n", pod)

	prunePendingPods(t_unix)

	pendingPods = append(pendingPods, pod)
}

func prunePendingPods(t_unix int64) {
	var first_idx = 0

	origLen := len(pendingPods)
	ageBound := t_unix - maxAgeSeconds
	for idx, pp := range pendingPods {
		first_idx = idx
		if pp.t_unix >= ageBound {
			break
		}
	}

	// prun away t_unix < ageBound, as these Pods are too old
	if first_idx > 0 {
		fmt.Printf("PrunePendingPods: taking range pendingPods[%d:%d]  so first pendingPod is %v\n", first_idx, origLen, pendingPods[first_idx])

		pendingPods = pendingPods[first_idx:]
	} else {
		fmt.Printf("PrunePendingPods: nothing to prune out of pendingPod list of length \n", origLen)
	}

}

func correctForPendingPods(nodeName string, nodeWatts int64) int64 {
	t_unix := getCurrentUnix()
	prunePendingPods(t_unix)

	for _, pp := range pendingPods {
		if pp.NodeName == nodeName {
			mWatts, ok := microWatts[pp.PodName]
			if ok {
				fmt.Printf("CorrForPending: correction for pod %s  of %d\n", pp.PodName, mWatts)
				nodeWatts += mWatts
			} else {
				fmt.Printf("CorrForPending: No Avg energy correction found for pod %s\n", pp.PodName)
			}
		} else {
			fmt.Printf("CorrForPending: no match of nodename %s  and %s\n", pp.NodeName, nodeName)
		}

	}

	return nodeWatts
}

type NodeCorrection struct {
	NodeName    string
	ExtraEnergy int64
}

func getNodeCorrections() ([]NodeCorrection, error) {
	var nodeCorr []NodeCorrection

	pods, err := getPods()
	if err != nil {
		return nodeCorr, fmt.Errorf("Failed to retrieve Pods-list. Error: %v", err)
	}

	for _, pod := range pods.Items {
		_, exists := ScaphPodLabels[pod.Metadata.Name]
		if exists {
			// this labels exists in Scaphandre, so we have a measurement for it.
			continue
		}

		// PodLabel does not exist, so comppute the correction
		basePodName := pod.Metadata.Labels["app"]
		podName := pod.Metadata.Name
		mWatts, ok := microWatts[basePodName]
		if ok {
			fmt.Printf("For the podName %s  instanciated as %s  found %d Milliwatts\n", &basePodName, &podName)
		} else {
			mWatts = int64(avgPodMicroWatts)
		}

		// and apply to the correct node
		nodeName := pod.Spec.NodeName
		found := false
		for _, nc := range nodeCorr {
			if nc.NodeName == nodeName {
				found = true
				nc.ExtraEnergy += mWatts
				break
			}
		}
		if !found {
			nodeCorr = append(nodeCorr, NodeCorrection{nodeName, mWatts})
		}
	}

	return nodeCorr, nil
}
