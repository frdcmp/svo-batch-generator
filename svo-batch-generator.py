import streamlit as st
import pandas as pd
import requests
import azure.cognitiveservices.speech as speechsdk
import os

# Load secrets from secrets.toml
speech_key, service_region, voices_endpoint = st.secrets["speech"].values()

# Configure the Streamlit app layout
st.set_page_config(layout="wide")
st.title("SVO Voice Generator")

# Function to fetch voices
def fetch_voices():
    try:
        response = requests.get(voices_endpoint, headers={"Ocp-Apim-Subscription-Key": speech_key})
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        return None

# Function to synthesize speech
def text_to_speech(audio_format, text, selected_voice, use_ssml, lexicon):
    if use_ssml:
        # Use ssml_indent for SSML text with prefix and suffix
        text = ssml_indent(text, generation_voice, lexicon)
        st.write(text)
    try:
        speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
        speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Audio48Khz192KBitRateMonoMp3 if audio_format == "mp3"
            else speechsdk.SpeechSynthesisOutputFormat.Riff48Khz16BitMonoPcm
        )
        speech_config.speech_synthesis_voice_name = selected_voice

        speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)
        result = speech_synthesizer.speak_ssml_async(text).get() if use_ssml else speech_synthesizer.speak_text_async(text).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            st.success("Speech synthesized successfully.")
            st.audio(result.audio_data)
        elif result.reason == speechsdk.ResultReason.Canceled:
            details = result.cancellation_details
            st.error(f"Speech synthesis canceled: {details.reason}")
            st.error(f"Error details: {details.error_details}" if details.reason == speechsdk.CancellationReason.Error else "")
            st.warning("Did you update the subscription info?")
    except Exception as e:
        st.error(f"An error occurred during text-to-speech conversion: {str(e)}")
    return result


# Function to indent the SSML text
def lexicon_indent(xml_url):
    # Check if xml_url is empty
    if not xml_url:
        return ""

    # Create the Lexicon string
    lexicon = f'''<lexicon uri="{xml_url}" />'''
    return lexicon


# Function to indent the SSML text
def ssml_indent(text, voice, lexicon):
    # Create the SSML string
    ssml = f'''<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="{lang_code}"><voice name="{voice}">{lexicon}{text}</voice></speak>'''
    return ssml

# Function to read Excel file and display DataFrame
def read_excel(file_path):
    df = pd.read_excel(file_path)
    st.dataframe(df)

# Function to replace words in the df_excel
def ssml_alias(df_pronunciation, df_excel):
    for _, row_pronunciation in df_pronunciation.iterrows():
        word_to_replace = row_pronunciation.iloc[0]
        replacement_word = row_pronunciation.iloc[1]

        df_excel.iloc[:, 1] = df_excel.iloc[:, 1].replace(word_to_replace, replacement_word, regex=True)
        
    return df_excel


def batch_text_to_speech(df_batch, audio_format, generation_voice, lang_code, lexicon):
    try:
        # Load data from Excel file
        #df_batch = pd.read_excel(file_path, header=None, skiprows=1, names=["File Names", "Text"])
        synthesis_results = []
        total_rows = len(df_batch)
        with st.spinner('Generating the TTS...'):
            my_bar = st.progress(0)
            for index, row in df_batch.iterrows():
                text = row.iloc[1]

                # Use ssml_indent for SSML text with prefix and suffix
                text = ssml_indent(text, generation_voice, lexicon)

                file_name = row.iloc[0]  # Use the first column (Column 1) for file names
                speech_output_path = os.path.join("./output", f"{file_name}.{audio_format}")

                try:
                    # Configure speech synthesis
                    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
                    speech_config.set_speech_synthesis_output_format(
                        speechsdk.SpeechSynthesisOutputFormat.Audio48Khz192KBitRateMonoMp3 if audio_format == "mp3"
                        else speechsdk.SpeechSynthesisOutputFormat.Riff48Khz16BitMonoPcm
                    )
                    speech_config.speech_synthesis_voice_name = generation_voice

                    # Perform text-to-speech synthesis
                    speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)
                    result = speech_synthesizer.speak_ssml_async(text).get() if use_ssml else speech_synthesizer.speak_text_async(text).get()

                    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                        synthesis_results.append({"file_name": file_name, "success": True, "output_path": speech_output_path})
                        # Save the audio file
                        with open(speech_output_path, "wb") as f:
                            f.write(result.audio_data)
                    else:
                        details = result.cancellation_details
                        error_message = f"Speech synthesis canceled for '{file_name}': {details.reason}"
                        st.error(error_message)
                        synthesis_results.append({"file_name": file_name, "success": False, "error_message": error_message})

                except Exception as e:
                    error_message = f"An error occurred during text-to-speech conversion for '{file_name}': {str(e)}"
                    st.error(error_message)
                    synthesis_results.append({"file_name": file_name, "success": False, "error_message": error_message})

                # Update progress bar
                my_bar.progress((index + 1) / total_rows)

        # Display summary message
        num_success = sum(result["success"] for result in synthesis_results)
        num_errors = len(synthesis_results) - num_success

        st.info(f"Text-to-speech synthesis completed.\n\n"
                f"Files generated successfully: {num_success}\n"
                f"Files with errors: {num_errors}")
        # Input field to specify the folder name within the 'audio' directory
        network_path = r"\\\lion\docker\svo-batch-generator\output"
        
        st.write("Location:")
        st.info(network_path)

        return synthesis_results

    except Exception as e:
        st.error(f"An error occurred during batch text-to-speech conversion: {str(e)}")
        return []


# Fetch voices
voices_data = fetch_voices()
df = pd.DataFrame(voices_data) if voices_data else pd.DataFrame()
excel_files = [file for file in os.listdir('./input') if file.endswith('.xlsx')]

with st.expander("Select Voice", expanded=True):
    # Create a multibox to select the voice by 'Locale, ShortName, and Gender'
    selected_voice_index = st.selectbox("Select a voice:", df.index,
                                        format_func=lambda i: f"{df.loc[i, 'Locale']}_{df.loc[i, 'DisplayName']}_{df.loc[i, 'Gender']}")
    generation_voice = df.loc[selected_voice_index, 'ShortName']
    lang_code = df.loc[selected_voice_index, 'Locale']



    audio_format = st.selectbox("Select a format for the audio file:", ["wav", "mp3"])


with st.expander("Pronunciation Guideline", expanded=False):
    xml_url = st.text_input("Input the XML url", value="https://ttslexicon.blob.core.windows.net/ttslexicon/lexicon.xml")
    lexicon = lexicon_indent(xml_url)
    if st.button("Test Lexicon"):
        lexicon = lexicon_indent(xml_url)
        
        try:
            response = requests.get(xml_url)
            xml_content = response.text
            st.code(xml_content, language='xml')
        except requests.exceptions.RequestException as e:
            st.error(f"Error fetching XML content: {e}")


    # Input field link to the lexicon folder
    lexicons_path = "https://portal.azure.com/#view/Microsoft_Azure_Storage/ContainerMenuBlade/~/overview/storageAccountId/%2Fsubscriptions%2Fc8ed5b2d-92d6-4b5d-8e7b-933a6840a29b%2FresourceGroups%2FAndovarTTS%2Fproviders%2FMicrosoft.Storage%2FstorageAccounts%2Fttslexicon/path/ttslexicon/etag/%220x8DC25C88DEFEB79%22/defaultEncryptionScope/%24account-encryption-key/denyEncryptionScopeOverride~/false/defaultId//publicAccessVal/Container"
    
    st.write("Lexicons:")
    st.info(lexicons_path)


with st.expander("Test Single Audio", expanded=False):   
    # Input for the text to be synthesized
    placeholder_text = "Input your text here..."
    text = st.text_area("Text to synthesize:", value=placeholder_text)

    # Checkbox to switch between plain text and SSML input
    use_ssml = st.checkbox("Use SSML Input", value = True)

    # Button to trigger speech synthesis
    if st.button("Synthesize Single Audio"):
        if text == placeholder_text:
            st.warning("Please enter some text or SSML to synthesize.")
        else:
            text_to_speech(audio_format, text, generation_voice, use_ssml, lexicon)


st.header("Generate Multiple Files")


# Input field to specify the folder name within the 'audio' directory
network_path = r"\\\lion\docker\svo-batch-generator\input"
st.info(network_path)
# Create a file uploader widget
uploaded_file = st.file_uploader("Upload a file", type=["csv", "txt", "xlsx"])

if uploaded_file is None:
    st.warning("Please upload an Excel file.")
else:
    df_excel = pd.read_excel(uploaded_file)
    col1, col2 = st.columns([1, 2])
    with col1:
        # Let the user select the column for 'ID'
        id_column = st.selectbox("Select Column for 'File Names'", df_excel.columns)
    with col2:
        # Let the user select the column for 'Script'
        script_column = st.selectbox("Select Column for 'Audio Script'", df_excel.columns)
    # Create a DataFrame 'df' with 'ID' and 'Script' columns
    df = pd.DataFrame({
        'File Names': df_excel[id_column],
        'Text': df_excel[script_column]
    })
    # Load Excel file from ./input folder
    #selected_excel_file = st.selectbox("Select Excel file:", excel_files)

    # Display selected Excel file
    #df_excel = pd.read_excel(os.path.join('./input', selected_excel_file))
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Button to trigger batch speech synthesis
    if st.button("Batch Synthesize Speech"):
        #file_path = os.path.join('./input', selected_excel_file)
        batch_text_to_speech(df, audio_format, generation_voice, lang_code, lexicon)