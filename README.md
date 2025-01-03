![Vocalearn_Logo_1](https://github.com/user-attachments/assets/eea1cf83-f115-4678-b3c6-88e738326827)

<h1>Vocalearn (AI Enhanced)</h1>
<h3>A robust backend service powering Vocalearn, a language learning platform that leverages Azure AI services to provide advanced language learning capabilities including translation, transcription, and pronunciation assessment.</h3>

<h2>✨ Core Capabilities</h2>
<ul>
  <li>
    <h3><b>Language Translation:</b> Seamlessly translate text between 100+ languages using Azure's AI translation services.</h3>
  </li>
  <li>
    <h3><b>Transcription:</b> Convert audio content to text across 100+ languages with high accuracy.</h3>
  </li>
  <li>
    <h3><b>Pronunciation Assessment:</b> Get detailed pronunciation feedback with scores for accuracy, prosody, fluency, and completeness in 35 different languages.</h3>
  </li>
  <li>
    <h3><b>Flexible Audio Input:</b> Handle both audio file uploads and direct recordings.</h3>
  </li>
    <li>
    <h3><b>Audio Processing:</b> Automatic audio conversion and optimization using FFmpeg for Azure AI compatibility.</h3>
  </li>
</ul>

<br />
<br />


<h2>🛠️ Tech Stack</h2>

![Django](https://img.shields.io/badge/django-%23092E20.svg?style=for-the-badge&logo=django&logoColor=white)
![Azure](https://img.shields.io/badge/azure-%230072C6.svg?style=for-the-badge&logo=microsoftazure&logoColor=white)


<ul>
  <li><h3>Django</h3></li>
  <li><h3>Azure AI Services integration</h3></li>
  <li><h3>FFmpeg integration for audio processing</h3></li>
  <li><h3>Scalable architecture</h3></li>
</ul>

<br />
<br />



<h2>📥 Installation</h2>

<h3>1.Clone the repository:</h3>

```bash
git clone https://github.com/sikatanju/vocalearn-backend.git
```
<h3>2.Navigate to the project directory:</h3>

```bash
cd vocalearn-backend
```
<h3>3.Install FFmpeg:</h3>

<ul>
  <li>
    <h3>Linux:</h3>
    
  ```bash
  sudo apt update
  sudo apt install ffmpeg
  ```
  </li>
  <li>
    <h3>macOS:</h3>
    
  ```bash
  brew install ffmpeg
  ```
  </li>
  <li>
    <h3>Windows:</h3>
    <ul>
      <li><h4>Download from FFmpeg official website</h4></li>
      <li><h4>Add FFmpeg to your system's PATH</h4></li>
    </ul>
  </li>
</ul>


<h3>4.Create and activate a virtual environment:</h3>

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```
<h3>5.Install dependencies:</h3>
Set up environment variables:

```bash
pip install -r requirements.txt
```

<h3>6.Set up environment variables:</h3>

```bash
cp .env.example .env
```

<h4>7. Start the development server:</h4>

```bash
py manage.py runserver
```

<br />
<br />


<h2>🔑 Environment Variables</h2>

<h3>Create a <span>.env</span> file in the root directory with the following variables:</h3>


<h2>⚙️Environment Variables</h2>
<h3>The system uses FFmpeg to process audio files before sending them to Azure AI services.</h3>
 
<h3>This includes:</h3>
<ul>
  <li><h4>Converting audio to the required format (WAV)</h4></li>
  <li><h4>Setting appropriate bitrate and sample rate</h4></li>
  <li><h4>Ensuring mono channel audio when required</h4></li>
  <li><h4>Optimizing audio quality for best recognition results</h4></li>
</ul>

<br />
<br />

<h2>🤝 Contributing</h2>

<h3>Contributions are welcome! Please feel free to submit a Pull Request.</h3>

<h3>1. Fork the project</h3>
<h3>2. Create your feature branch (git checkout -b feature/AmazingFeature)</h3>
<h3>3. Commit your changes (git commit -m 'Add some AmazingFeature')</h3>
<h3>4. Push to the branch (git push origin feature/AmazingFeature)</h3>
<h3>5. Open a Pull Request</h3>

<br />
<br />
<h2>📝 License</h2>

This project is licensed under the MIT License - see the LICENSE file for details.
