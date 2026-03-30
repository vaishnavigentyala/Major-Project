import requests
import sys
import json
from datetime import datetime

class CareerGuidanceAPITester:
    def __init__(self, base_url="https://edupathfinder-9.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.student_id = None
        self.tests_run = 0
        self.tests_passed = 0

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        if headers is None:
            headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=30)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    print(f"   Response keys: {list(response_data.keys()) if isinstance(response_data, dict) else 'Non-dict response'}")
                    return True, response_data
                except:
                    return True, response.text
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Error text: {response.text}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_root_endpoint(self):
        """Test the root API endpoint"""
        return self.run_test("Root API", "GET", "", 200)

    def test_create_student(self):
        """Test student profile creation"""
        student_data = {
            "name": f"Test Student {datetime.now().strftime('%H%M%S')}",
            "email": f"test{datetime.now().strftime('%H%M%S')}@example.com",
            "age": 18,
            "grade_level": "12th Grade",
            "gpa": 3.8,
            "subjects": {
                "Mathematics": 95.0,
                "Science": 88.0,
                "English": 92.0,
                "Social Studies": 85.0,
                "Programming": 90.0
            }
        }
        
        success, response = self.run_test(
            "Create Student Profile",
            "POST",
            "students",
            200,
            data=student_data
        )
        
        if success and 'id' in response:
            self.student_id = response['id']
            print(f"   Student ID: {self.student_id}")
            return True
        return False

    def test_get_student(self):
        """Test retrieving student profile"""
        if not self.student_id:
            print("❌ No student ID available for testing")
            return False
            
        return self.run_test(
            "Get Student Profile",
            "GET",
            f"students/{self.student_id}",
            200
        )[0]

    def test_aptitude_test(self):
        """Test aptitude test submission"""
        if not self.student_id:
            print("❌ No student ID available for testing")
            return False
            
        aptitude_data = {
            "student_id": self.student_id,
            "technical_answers": {
                "q1": "b",  # Correct answer
                "q2": "c",  # Correct answer
                "q3": "a",  # Correct answer
                "q4": "b",  # Correct answer
                "q5": "c"   # Correct answer
            },
            "creative_answers": {
                "q1": "Implement a community recycling program with rewards",
                "q2": "An app that connects students with local volunteer opportunities",
                "q3": "Smart art installations that respond to environmental data",
                "q4": "Interactive learning spaces with VR and collaborative zones",
                "q5": "Solar-powered charging stations for rural communities"
            }
        }
        
        return self.run_test(
            "Submit Aptitude Test",
            "POST",
            "aptitude-test",
            200,
            data=aptitude_data
        )[0]

    def test_behavioral_test(self):
        """Test behavioral test submission"""
        if not self.student_id:
            print("❌ No student ID available for testing")
            return False
            
        behavioral_data = {
            "student_id": self.student_id,
            "answers": {
                "q1": "a",
                "q2": "a",
                "q3": "a",
                "q4": "a",
                "q5": "AI, Technology, Innovation, Problem Solving",
                "q6": "a",
                "q7": "a",
                "q8": "a"
            }
        }
        
        return self.run_test(
            "Submit Behavioral Test",
            "POST",
            "behavioral-test",
            200,
            data=behavioral_data
        )[0]

    def test_career_prediction(self):
        """Test career prediction generation"""
        if not self.student_id:
            print("❌ No student ID available for testing")
            return False
            
        print(f"\n🤖 Testing GPT-5.1 Career Prediction (this may take 10-30 seconds)...")
        return self.run_test(
            "Generate Career Prediction",
            "POST",
            f"predict-career/{self.student_id}",
            200
        )[0]

    def test_get_prediction(self):
        """Test retrieving career prediction"""
        if not self.student_id:
            print("❌ No student ID available for testing")
            return False
            
        return self.run_test(
            "Get Career Prediction",
            "GET",
            f"prediction/{self.student_id}",
            200
        )[0]

def main():
    print("🚀 Starting Career Guidance System API Tests")
    print("=" * 60)
    
    tester = CareerGuidanceAPITester()
    
    # Test sequence
    tests = [
        ("Root API", tester.test_root_endpoint),
        ("Student Creation", tester.test_create_student),
        ("Student Retrieval", tester.test_get_student),
        ("Aptitude Test", tester.test_aptitude_test),
        ("Behavioral Test", tester.test_behavioral_test),
        ("Career Prediction (GPT-5.1)", tester.test_career_prediction),
        ("Prediction Retrieval", tester.test_get_prediction)
    ]
    
    failed_tests = []
    
    for test_name, test_func in tests:
        try:
            if not test_func():
                failed_tests.append(test_name)
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {str(e)}")
            failed_tests.append(test_name)
    
    # Print results
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {tester.tests_passed}/{tester.tests_run} passed")
    
    if failed_tests:
        print(f"❌ Failed tests: {', '.join(failed_tests)}")
        return 1
    else:
        print("✅ All tests passed!")
        return 0

if __name__ == "__main__":
    sys.exit(main())