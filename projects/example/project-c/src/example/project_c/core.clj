(ns example.project-c.core
  (:require [clojure.string :as str]
            [cheshire.core :as json]
            [example.project-a.core :refer [thing]]))

(defn transform-project-a []
  (str/upper-case thing))

(defn thing-as-json []
  (json/generate-string {:value thing}))