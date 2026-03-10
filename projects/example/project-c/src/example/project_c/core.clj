(ns example.project-c.core
  (:require [clojure.string :as str]
            [example.project-a.core :refer [thing]]))

(defn transform-project-a []
  (str/upper-case thing))