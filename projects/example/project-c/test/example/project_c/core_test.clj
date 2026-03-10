(ns example.project-c.core-test
  (:require [clojure.test :refer [deftest is]]
            [example.project-a.core :refer [thing]]
            [example.project-c.core :as core]))

(deftest test-transform-project-a
  (is (= "EXAMPLE COMMON VALUE" (core/transform-project-a))))

(deftest test-project-a-value
  (is (= "example common value" thing)))