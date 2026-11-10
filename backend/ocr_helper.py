import json
import re

from collections import defaultdict, deque

import cv2


try:
    from paddleocr import PaddleOCR

    PADDLE_AVAILABLE = True
    PADDLE_IMPORT_ERROR = None

except Exception as import_error:

    PaddleOCR = None
    PADDLE_AVAILABLE = False
    PADDLE_IMPORT_ERROR = import_error


class PlateReader:

    HIGH_CONFIDENCE_THRESHOLD = 0.95

    PLATE_PATTERN = re.compile(
        r"^[A-Z]{2}\d{2}[A-Z]{1,3}\d{4}$"
    )

    MIN_CONFIDENCE = 0.35
    MIN_VOTES = 3
    MIN_CHARACTER_AGREEMENT = 0.60
    VOTE_WINDOW = 15

    def __init__(self):

        self.reader = None

        self.plate_votes = defaultdict(
            lambda: deque(maxlen=self.VOTE_WINDOW)
        )

        self.stable_plates = {}
        self.stable_confidence = {}

        self.best_quality = {}
        self.best_crops = {}

        if not PADDLE_AVAILABLE:

            print(
                "[OCR] PaddleOCR could not be imported. "
                "OCR is disabled. "
                f"Reason: {PADDLE_IMPORT_ERROR}"
            )

            return

        print("[OCR] Initializing PaddleOCR...")

        try:

            self.reader = PaddleOCR(
                lang="en",
                enable_mkldnn=False,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False
            )

            print(
                "[OCR] PaddleOCR initialized successfully."
            )

        except Exception as error:

            self.reader = None

            print(
                f"[OCR INIT ERROR] {error}"
            )


    # ---------------- TEXT CLEANING ----------------

    @staticmethod
    def clean_text(text):

        if text is None:
            return ""

        return re.sub(
            r"[^A-Z0-9]",
            "",
            str(text).upper()
        )


    # ---------------- PLATE VALIDATION ----------------

    @classmethod
    def is_valid_plate(cls, text):

        return bool(
            cls.PLATE_PATTERN.fullmatch(text)
        )


    # ---------------- BEST PLATE MANAGEMENT ----------------

    def update_stable_plate(
        self,
        track_key,
        candidate,
        confidence
    ):

        candidate = self.clean_text(candidate)

        if not self.is_valid_plate(candidate):
            return False

        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            return False

        if confidence < self.MIN_CONFIDENCE:
            return False

        previous_confidence = self.stable_confidence.get(
            track_key,
            -1.0
        )

        # Never replace a better accepted result
        # with a lower-confidence result.

        if confidence <= previous_confidence:
            return False

        previous_plate = self.stable_plates.get(
            track_key,
            "SCANNING"
        )

        self.stable_plates[track_key] = candidate
        self.stable_confidence[track_key] = confidence

        print(
            f"[BEST PLATE UPDATED] Track {track_key} | "
            f"{previous_plate} -> {candidate} | "
            f"Confidence: {confidence:.4f}"
        )

        return True


    # ---------------- IMAGE QUALITY ----------------

    @staticmethod
    def calculate_quality(crop):

        if crop is None or crop.size == 0:
            return 0.0

        gray = cv2.cvtColor(
            crop,
            cv2.COLOR_BGR2GRAY
        )

        sharpness = cv2.Laplacian(
            gray,
            cv2.CV_64F
        ).var()

        return float(sharpness)


    @staticmethod
    def normalize_quality(quality):

        return quality / (quality + 100.0)


    def update_best_crop(
        self,
        track_key,
        crop,
        quality
    ):

        previous_quality = self.best_quality.get(
            track_key,
            -1.0
        )

        if quality > previous_quality:

            self.best_quality[track_key] = quality

            self.best_crops[track_key] = crop.copy()

            print(
                f"[BEST FRAME] Track {track_key} | "
                f"Sharpness: {quality:.2f}"
            )


    # ---------------- MODERN OCR RESULT PARSING ----------------

    def _parse_modern_result(self, result):

        payload = None

        if isinstance(result, dict):

            payload = result

        else:

            try:

                payload = result.json

                if callable(payload):
                    payload = payload()

            except Exception:
                payload = None

            if payload is None:

                try:
                    payload = result.res

                except Exception:
                    payload = None

        if isinstance(payload, str):

            try:
                payload = json.loads(payload)

            except json.JSONDecodeError:
                return []

        if not isinstance(payload, dict):
            return []

        payload = payload.get("res", payload)

        if not isinstance(payload, dict):
            return []

        texts = payload.get("rec_texts", []) or []
        scores = payload.get("rec_scores", []) or []

        parsed = []

        for index, text in enumerate(texts):

            try:

                score = (
                    float(scores[index])
                    if index < len(scores)
                    else 0.0
                )

            except (TypeError, ValueError):
                score = 0.0

            cleaned = self.clean_text(text)

            if (
                cleaned
                and score >= self.MIN_CONFIDENCE
            ):

                parsed.append(
                    (cleaned, score)
                )

        return parsed


    # ---------------- LEGACY OCR RESULT PARSING ----------------

    def _parse_legacy_result(self, node):

        parsed = []

        if not isinstance(node, (list, tuple)):
            return parsed

        if (
            len(node) >= 2
            and isinstance(node[1], (list, tuple))
            and len(node[1]) >= 2
            and isinstance(node[1][0], str)
        ):

            cleaned = self.clean_text(node[1][0])

            try:
                score = float(node[1][1])

            except (TypeError, ValueError):
                score = 0.0

            if (
                cleaned
                and score >= self.MIN_CONFIDENCE
            ):

                parsed.append(
                    (cleaned, score)
                )

            return parsed

        for child in node:

            parsed.extend(
                self._parse_legacy_result(child)
            )

        return parsed


    # ---------------- GENERAL RESULT PARSER ----------------

    def parse_results(self, results):

        if results is None:
            return []

        parsed = []

        if not isinstance(results, (list, tuple)):
            results = [results]

        for result in results:

            modern = self._parse_modern_result(result)

            if modern:

                parsed.extend(modern)

            else:

                parsed.extend(
                    self._parse_legacy_result(result)
                )

        return parsed


    # ---------------- IMAGE PREPARATION ----------------

    @staticmethod
    def prepare_crops(crop):

        if crop is None or crop.size == 0:
            return []

        enlarged = cv2.resize(
            crop,
            None,
            fx=3,
            fy=3,
            interpolation=cv2.INTER_CUBIC
        )

        gray = cv2.cvtColor(
            enlarged,
            cv2.COLOR_BGR2GRAY
        )

        clahe = cv2.createCLAHE(
            clipLimit=2.0,
            tileGridSize=(8, 8)
        )

        enhanced = clahe.apply(gray)

        enhanced_bgr = cv2.cvtColor(
            enhanced,
            cv2.COLOR_GRAY2BGR
        )

        blurred = cv2.GaussianBlur(
            enlarged,
            (0, 0),
            2.0
        )

        sharpened = cv2.addWeighted(
            enlarged,
            1.5,
            blurred,
            -0.5,
            0
        )

        return [
            crop,
            enlarged,
            enhanced_bgr,
            sharpened
        ]


    # ---------------- CACHED PLATE ----------------

    def get_cached_plate(self, track_key):

        return self.stable_plates.get(
            track_key,
            "SCANNING"
        )


    def get_cached_confidence(self, track_key):

        return self.stable_confidence.get(
            track_key,
            0.0
        )


    # ---------------- MULTI-FRAME VOTING ----------------

    def get_stable_plate(
        self,
        track_key,
        candidate,
        confidence,
        quality=0.0,
        single_frame=False
    ):

        candidate = self.clean_text(candidate)

        try:

            confidence = float(confidence)
            quality = float(quality)

        except (TypeError, ValueError):

            return self.get_cached_plate(track_key)

        if (
            not self.is_valid_plate(candidate)
            or confidence < self.MIN_CONFIDENCE
        ):

            return self.get_cached_plate(track_key)


        # ACCEPT IMMEDIATELY IF SINGLE FRAME OR HIGH CONFIDENCE
        if single_frame or confidence >= self.HIGH_CONFIDENCE_THRESHOLD:

            self.update_stable_plate(
                track_key,
                candidate,
                confidence
            )

            return self.get_cached_plate(track_key)


        # NORMAL MULTI-FRAME VOTING

        quality_weight = self.normalize_quality(
            max(quality, 0.0)
        )

        vote_weight = confidence * (
            0.25 + 0.75 * quality_weight
        )

        votes = self.plate_votes[track_key]

        votes.append(
            (candidate, vote_weight, confidence)
        )

        print(
            f"[VOTE DEBUGGING] TRACK:{track_key} | "
            f"Candidate:{candidate} | "
            f"Confidence:{confidence:.2f} | "
            f"TOTAL VOTES:{len(votes)}"
        )

        length_counts = defaultdict(int)

        for plate, weight, score in votes:

            length_counts[len(plate)] += 1

        if not length_counts:
            return self.get_cached_plate(track_key)

        best_length = max(
            length_counts,
            key=length_counts.get
        )

        same_length_votes = [
            (plate, weight, score)
            for plate, weight, score in votes
            if len(plate) == best_length
        ]

        if len(same_length_votes) < self.MIN_VOTES:

            return self.get_cached_plate(track_key)

        winning_plate = []

        for position in range(best_length):

            character_weights = defaultdict(float)

            total_weight = 0.0

            for plate, weight, score in same_length_votes:

                character_weights[
                    plate[position]
                ] += weight

                total_weight += weight

            if (
                not character_weights
                or total_weight <= 0
            ):

                return self.get_cached_plate(track_key)

            best_character = max(
                character_weights,
                key=character_weights.get
            )

            agreement = (
                character_weights[best_character]
                / total_weight
            )

            if agreement < self.MIN_CHARACTER_AGREEMENT:

                return self.get_cached_plate(track_key)

            winning_plate.append(best_character)

        voted_plate = "".join(winning_plate)

        if self.is_valid_plate(voted_plate):

            # Confidence of the consensus is calculated
            # from the observations contributing to the vote.

            total_vote_weight = sum(
                weight
                for plate, weight, score in same_length_votes
            )

            if total_vote_weight <= 0:
                return self.get_cached_plate(track_key)

            voted_confidence = sum(
                weight * score
                for plate, weight, score in same_length_votes
            ) / total_vote_weight

            self.update_stable_plate(
                track_key,
                voted_plate,
                voted_confidence
            )

            return self.get_cached_plate(track_key)

        return self.get_cached_plate(track_key)


    # ---------------- OCR EXTRACTION ----------------

    def extract_plate_number(
        self,
        frame,
        bbox,
        track_key,
        single_frame=False
    ):

        if self.reader is None:

            return self.get_cached_plate(track_key)

        try:

            x1, y1, x2, y2 = map(
                int,
                bbox
            )

        except (TypeError, ValueError):

            return self.get_cached_plate(track_key)

        frame_height, frame_width = frame.shape[:2]

        pad_x = int(
            max(0, x2 - x1) * 0.12
        )

        pad_y = int(
            max(0, y2 - y1) * 0.12
        )

        x1 = max(0, x1 - pad_x)
        y1 = max(0, y1 - pad_y)

        x2 = min(frame_width, x2 + pad_x)
        y2 = min(frame_height, y2 + pad_y)

        if x2 <= x1 or y2 <= y1:

            return self.get_cached_plate(track_key)

        crop = frame[y1:y2, x1:x2]

        if crop.size == 0:
            return self.get_cached_plate(track_key)

        quality = self.calculate_quality(crop)

        self.update_best_crop(
            track_key,
            crop,
            quality
        )

        prepared_crops = self.prepare_crops(crop)

        candidates = []

        for processed_crop in prepared_crops:

            try:

                if hasattr(self.reader, "predict"):

                    results = self.reader.predict(
                        processed_crop
                    )

                else:

                    results = self.reader.ocr(
                        processed_crop,
                        cls=False
                    )

                parsed_results = self.parse_results(
                    results
                )

                for text, score in parsed_results:

                    if self.is_valid_plate(text):

                        candidates.append(
                            (text, score)
                        )

            except Exception as error:

                print(
                    f"[OCR ERROR] Track {track_key}: {error}"
                )

        if not candidates:

            return self.get_cached_plate(track_key)

        # Select the highest-confidence result from this frame.
        # Preprocessing variants count as one OCR attempt.

        best_text, best_score = max(
            candidates,
            key=lambda item: item[1]
        )

        print(
            f"[RAW OCR] Track: {track_key} | "
            f"Text: {best_text} | "
            f"Confidence: {best_score:.2f} | "
            f"Sharpness: {quality:.2f}"
        )

        return self.get_stable_plate(
            track_key,
            best_text,
            best_score,
            quality,
            single_frame=single_frame
        )


    # ---------------- TRACK CLEANUP ----------------

    def clear_track(self, track_key):

        self.plate_votes.pop(
            track_key,
            None
        )

        self.stable_plates.pop(
            track_key,
            None
        )

        self.stable_confidence.pop(
            track_key,
            None
        )

        self.best_quality.pop(
            track_key,
            None
        )

        self.best_crops.pop(
            track_key,
            None
        )